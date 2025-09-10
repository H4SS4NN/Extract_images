"""
Extracteur PDF principal
"""
import os
import cv2
import numpy as np
import json
import time
from datetime import datetime
from pathlib import Path
from pdf2image import convert_from_path
import PyPDF2

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from utils import logger, FileUtils, ImageUtils
from config import OUTPUT_BASE_DIR, DETECTION_CONFIG
from detectors.ultra_detector import UltraDetector
from detectors.template_detector import TemplateDetector
from detectors.color_detector import ColorDetector
from analyzers.coherence_analyzer import CoherenceAnalyzer
from analyzers.quality_analyzer import QualityAnalyzer
from analyzers.summary_analyzer import SummaryAnalyzer
from analyzers.final_json_generator import FinalJSONGenerator
from toc_planches import (extract_toc_from_pdf, extract_toc_from_pdf_multipage, build_plate_map, 
                         save_toc_json, apply_renaming, prompt_for_renaming, 
                         extract_artist_name_from_pdf, create_artwork_jsons_for_images)
from artwork_collections import CollectionFactory

class PDFExtractor:
    """Extracteur PDF principal avec architecture modulaire"""
    
    def __init__(self, collection_name: str = None, skip_toc_search: bool = False):
        self.output_base_dir = OUTPUT_BASE_DIR
        self.session_dir = None
        self.total_extracted = 0
        self.skip_toc_search = skip_toc_search  # Option pour désactiver la recherche sommaire
        
        # Initialiser la collection d'artiste
        self.collection = self._initialize_collection(collection_name)
        
        # Initialiser les composants
        self.detectors = [
            UltraDetector(),
            TemplateDetector(),
            ColorDetector()
        ]
        self.coherence_analyzer = CoherenceAnalyzer()
        self.quality_analyzer = QualityAnalyzer()
        self.summary_analyzer = SummaryAnalyzer()
        self.final_json_generator = FinalJSONGenerator()
        
        # Configuration Tesseract
        self._configure_tesseract()
    
    def _initialize_collection(self, collection_name: str = None):
        """Initialise la collection d'artiste"""
        if collection_name:
            collection = CollectionFactory.create_collection(collection_name)
            if collection:
                logger.info(f"✅ Collection sélectionnée: {collection.name}")
                return collection
            else:
                logger.warning(f"⚠️ Collection '{collection_name}' non trouvée, utilisation de Picasso par défaut")
        
        # Collection par défaut (Picasso pour compatibilité)
        collection = CollectionFactory.create_collection(CollectionFactory.get_default_collection())
        logger.info(f"📚 Collection par défaut: {collection.name}")
        return collection
    
    def set_collection(self, collection_name: str) -> bool:
        """Change la collection utilisée"""
        new_collection = CollectionFactory.create_collection(collection_name)
        if new_collection:
            self.collection = new_collection
            logger.info(f"✅ Collection changée vers: {new_collection.name}")
            return True
        else:
            logger.error(f"❌ Collection '{collection_name}' non trouvée")
            return False
    
    def get_available_collections(self):
        """Retourne les collections disponibles"""
        return CollectionFactory.get_available_collections()
    
    def auto_detect_collection(self, pdf_path: str, extracted_text: str = "") -> str:
        """Détecte automatiquement la collection"""
        detected = CollectionFactory.auto_detect_collection(pdf_path, extracted_text)
        if detected:
            logger.info(f"🔍 Collection détectée automatiquement: {detected}")
            self.set_collection(detected)
        return detected
    
    def _configure_tesseract(self):
        """Configure Tesseract OCR"""
        import pytesseract
        from config import TESSERACT_PATHS
        
        for path in TESSERACT_PATHS:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"✅ Tesseract trouvé: {path}")
                return True
        
        logger.warning("⚠️ Tesseract non trouvé - OCR désactivé")
        return False
    
    def extract_pdf(self, pdf_path: str, max_pages: int = None, start_page: int = 1) -> bool:
        """Extraction complète d'un PDF"""
        if not os.path.exists(pdf_path):
            logger.error(f"❌ Fichier non trouvé: {pdf_path}")
            return False
        
        logger.info(f"🚀 EXTRACTION ULTRA SENSIBLE: {os.path.basename(pdf_path)}")
        
        # Créer la session
        pdf_name = os.path.basename(pdf_path)
        self.session_dir = FileUtils.create_session_folder(pdf_name, self.output_base_dir)
        
        # Compter les pages
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pdf_pages = len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"❌ Impossible de lire le PDF: {e}")
            return False
        
        # ÉTAPE 1: Chercher TABLE DES PLANCHES dans les 15 dernières pages
        toc_data = None
        plate_map = {}
        artist_name = "Artiste Inconnu"
        
        # ÉTAPE 1.5: Recherche de sommaire selon la collection
        if self.collection.has_summary_page() and not self.skip_toc_search:
            try:
                import time
                start_time = time.time()
                
                summary_config = self.collection.get_summary_detection_config()
                keywords = summary_config.get('keywords', [])
                logger.info(f"🔍 Recherche TABLE DES PLANCHES pour {self.collection.name} dans les 15 dernières pages...")
                logger.info(f"📋 Mots-clés de recherche: {keywords}")
                
                # Activer temporairement les logs DEBUG pour cette section
                import logging
                original_level = logger.logger.level
                logger.logger.setLevel(logging.DEBUG)
                
                try:
                    toc_data = extract_toc_from_pdf_multipage(pdf_path, last_n=15, keywords=keywords)
                    elapsed_time = time.time() - start_time
                    logger.info(f"⏱️ Recherche sommaire terminée en {elapsed_time:.2f}s")
                finally:
                    # Restaurer le niveau de log original
                    logger.logger.setLevel(original_level)
            if toc_data:
                plate_map = build_plate_map(toc_data)
                save_toc_json(toc_data, self.session_dir)
                logger.info(f"📋 {len(plate_map)} planches mappées")
                
                # Extraire le nom de l'artiste depuis le PDF
                artist_name = extract_artist_name_from_pdf(pdf_path)
                logger.info(f"🎨 Artiste détecté: {artist_name}")
                
                # Afficher les pages disponibles
                pages_with_plates = [p['page'] for p in toc_data['plates'] if p['page'] is not None]
                if pages_with_plates:
                    logger.info(f"📄 Pages contenant des planches: {sorted(set(pages_with_plates))}")
            else:
                logger.info("ℹ️ Aucune TABLE DES PLANCHES trouvée")
        except Exception as e:
            logger.warning(f"⚠️ Erreur extraction TOC: {e}")
        else:
            if self.skip_toc_search:
                logger.info(f"⚡ Recherche sommaire DÉSACTIVÉE (mode rapide)")
            else:
                logger.info(f"📋 Collection {self.collection.name}: Pas de recherche de sommaire (numéros directement sous les œuvres)")
            artist_name = self.collection.name  # Utiliser le nom de la collection comme artiste
        
        # ÉTAPE 2: Utiliser les paramètres saisis ou demander confirmation
        if toc_data and plate_map:
            # Proposer les pages avec des planches
            pages_with_plates = [p['page'] for p in toc_data['plates'] if p['page'] is not None]
            if pages_with_plates:
                unique_pages = sorted(set(pages_with_plates))
                logger.info(f"📋 Pages recommandées (avec planches): {unique_pages}")
                
                # Calculer la plage par défaut basée sur les paramètres saisis
                if start_page < 1 or start_page > total_pdf_pages:
                    logger.error(f"❌ start_page invalide: {start_page} (PDF = {total_pdf_pages} pages)")
                    return False

                if max_pages:
                    end_page = min(total_pdf_pages, start_page + max_pages - 1)
                else:
                    end_page = total_pdf_pages
                
                # Afficher la plage calculée et demander confirmation
                logger.info(f"📄 Plage calculée: {start_page} → {end_page} (total {end_page - start_page + 1} pages)")
                
                try:
                    user_input = input(f"📄 Confirmer cette plage ? [O/n] ou saisir une nouvelle plage: ").strip()
                    if user_input.lower() in ('', 'o', 'oui', 'y', 'yes'):
                        # Utiliser la plage calculée
                        pass
                    else:
                        # Parser la nouvelle plage
                        start_page, end_page = self._parse_page_range(user_input, total_pdf_pages)
                except (KeyboardInterrupt, EOFError):
                    logger.info("❌ Annulé par l'utilisateur")
                    return False
            else:
                # Pas de pages spécifiques, utiliser les paramètres saisis
                if start_page < 1 or start_page > total_pdf_pages:
                    logger.error(f"❌ start_page invalide: {start_page} (PDF = {total_pdf_pages} pages)")
                    return False

                if max_pages:
                    end_page = min(total_pdf_pages, start_page + max_pages - 1)
                else:
                    end_page = total_pdf_pages
        else:
            # Pas de TOC trouvé, utiliser les paramètres par défaut
            if start_page < 1 or start_page > total_pdf_pages:
                logger.error(f"❌ start_page invalide: {start_page} (PDF = {total_pdf_pages} pages)")
                return False

            # Calculer la plage
            if max_pages:
                end_page = min(total_pdf_pages, start_page + max_pages - 1)
            else:
                end_page = total_pdf_pages
        
        total_pages = end_page - start_page + 1
        logger.info(f"📄 Pages à traiter: {start_page} → {end_page} (total {total_pages})")
        
        # Stocker les données du sommaire pour utilisation immédiate
        self.plate_map = plate_map
        self.artist_name = artist_name
        self.current_pdf_path = pdf_path
        
        # Créer le fichier de résumé global
        global_log = {
            'pdf_name': pdf_name,
            'pdf_path': os.path.abspath(pdf_path),
            'session_dir': self.session_dir,
            'mode': 'ULTRA_SENSIBLE',
            'start_time': datetime.now().isoformat(),
            'total_pages': total_pages,
            'start_page': start_page,
            'end_page': end_page,
            'toc_found': toc_data is not None,
            'plate_count': len(plate_map),
            'pages': []
        }
        
        # Traiter chaque page
        for idx, page_num in enumerate(range(start_page, end_page + 1), start=1):
            logger.info(f"📄 Traitement page {page_num} ({idx}/{total_pages})")
            try:
                page_result = self.process_page(pdf_path, page_num)
                global_log['pages'].append(page_result)
                
                if page_result['success']:
                    self.total_extracted += page_result['images_extracted']
                    logger.info(f"  ✅ Page {page_num}: {page_result['images_extracted']} images capturées")
            except Exception as e:
                logger.error(f"  ❌ Erreur page {page_num}: {e}")
                # Ajouter une page d'erreur même en cas d'échec
                error_page = {
                    'page_number': page_num,
                    'success': False,
                    'images_extracted': 0,
                    'error': str(e),
                    'start_time': datetime.now().isoformat(),
                    'end_time': datetime.now().isoformat()
                }
                global_log['pages'].append(error_page)
            
            # Sauvegarder le log global après CHAQUE page (pour éviter la perte en cas d'interruption)
            global_log['end_time'] = datetime.now().isoformat()
            global_log['total_images_extracted'] = self.total_extracted
            global_log['success_pages'] = len([p for p in global_log['pages'] if p['success']])
            global_log['failed_pages'] = len([p for p in global_log['pages'] if not p['success']])
            
            # Sauvegarder le log global (mise à jour continue)
            global_log_path = os.path.join(self.session_dir, "extraction_ultra_complete.json")
            with open(global_log_path, 'w', encoding='utf-8') as f:
                json.dump(global_log, f, indent=2, ensure_ascii=False)
        
        # Créer le résumé texte
        self._create_text_summary(global_log)
        
        # NOUVEAU : Générer le JSON final pour l'interface web
        logger.info("🎯 Génération du JSON final pour l'interface web...")
        try:
            final_data = self.final_json_generator.generate_final_json(global_log, self.session_dir)
            
            # Créer des JSON individuels
            self.final_json_generator.create_individual_jsons(final_data, self.session_dir)
            
            # Créer le rapport de synthèse
            self.final_json_generator.create_summary_report(final_data, self.session_dir)
            
            logger.info("✅ JSON final généré avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur génération JSON final: {e}")
        
        logger.info(f"🎉 EXTRACTION TERMINÉE: {self.total_extracted} images extraites")
        logger.info(f"📁 Résultats: {self.session_dir}")
        
        # Apply renaming and create artwork JSONs if TOC was found
        if toc_data and plate_map:
            try:
                if prompt_for_renaming():
                    logger.info("🔄 Application du renommage...")
                    stats = apply_renaming(self.session_dir, plate_map, global_log)
                    
                    logger.info("📊 Résumé du renommage:")
                    logger.info(f"  • Total images: {stats['total_images']}")
                    logger.info(f"  • Renommées: {stats['renamed']}")
                    logger.info(f"  • Ignorées: {stats['skipped']}")
                    logger.info(f"  • Non trouvées: {stats['not_matched']}")
                    
                    # Les JSONs d'œuvres ont été créés immédiatement pendant l'extraction
                    logger.info("ℹ️ JSONs d'œuvres créés pendant l'extraction")
                else:
                    logger.info("ℹ️ Renommage annulé par l'utilisateur")
            except Exception as e:
                logger.error(f"❌ Erreur lors du renommage: {e}")
        
        # ÉTAPE POST-EXTRACTION: Résumé pour Dubuffet
        if self.collection.name.lower() == "dubuffet":
            logger.info("✅ Dubuffet: JSON créés immédiatement pour chaque image détectée")
            logger.info("🎨 OCR immédiat terminé - pas d'OCR global nécessaire")
        
        # Ouvrir le dossier automatiquement
        if os.name == 'nt':
            try:
                os.startfile(self.session_dir)
            except:
                pass
        
        return True
    
    def _parse_page_range(self, user_input: str, total_pages: int) -> tuple:
        """Parse user input for page range selection"""
        try:
            # Format: "1-50" ou "1,5,10" ou "1-10,20-30"
            if '-' in user_input:
                # Plage simple: "1-50"
                if ',' not in user_input:
                    start, end = user_input.split('-', 1)
                    start_page = max(1, int(start.strip()))
                    end_page = min(total_pages, int(end.strip()))
                    return start_page, end_page
                else:
                    # Plages multiples: "1-10,20-30"
                    ranges = user_input.split(',')
                    all_pages = set()
                    for range_str in ranges:
                        if '-' in range_str:
                            start, end = range_str.split('-', 1)
                            start_p = max(1, int(start.strip()))
                            end_p = min(total_pages, int(end.strip()))
                            all_pages.update(range(start_p, end_p + 1))
                        else:
                            page = int(range_str.strip())
                            if 1 <= page <= total_pages:
                                all_pages.add(page)
                    
                    if all_pages:
                        return min(all_pages), max(all_pages)
                    else:
                        return 1, total_pages
            else:
                # Pages individuelles: "1,5,10"
                pages = [int(p.strip()) for p in user_input.split(',')]
                valid_pages = [p for p in pages if 1 <= p <= total_pages]
                if valid_pages:
                    return min(valid_pages), max(valid_pages)
                else:
                    return 1, total_pages
                    
        except (ValueError, IndexError):
            logger.warning(f"⚠️ Format invalide: {user_input}. Utilisation de toutes les pages.")
            return 1, total_pages
    
    def process_page(self, pdf_path: str, page_num: int) -> dict:
        """Traite une page spécifique"""
        page_start_time = time.time()
        
        # Créer le dossier de la page
        page_dir = FileUtils.create_page_folder(self.session_dir, page_num)
        
        page_result = {
            'page_number': page_num,
            'page_dir': page_dir,
            'start_time': datetime.now().isoformat(),
            'mode': 'ULTRA_SENSIBLE',
            'success': False,
            'images_extracted': 0,
            'rectangles_found': 0,
            'images_saved': [],
            'rectangles_details': [],
            'error': None
        }
        
        try:
            # Analyser les dimensions de la page
            page_analysis = self._analyze_page_dimensions(pdf_path, page_num)
            page_result['page_analysis'] = page_analysis
            
            # Convertir la page avec DPI élevé
            high_dpi = max(400, page_analysis['recommended_dpi'])
            logger.info(f"  📏 Page {page_num}: {page_analysis['page_format']} → DPI {high_dpi}")
            
            # DEBUG: Log pour vérifier la cohérence des numéros de pages
            logger.debug(f"🔍 DEBUG: Conversion PDF page {page_num} depuis {pdf_path}")
            
            page_images = convert_from_path(
                pdf_path, 
                dpi=high_dpi,
                first_page=page_num,
                last_page=page_num
            )
            
            if not page_images:
                raise Exception("Conversion PDF échouée")
            
            page_image = page_images[0]
            page_array = np.array(page_image)
            page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
            
            page_result['image_size'] = f"{page_cv.shape[1]}×{page_cv.shape[0]}"
            page_result['image_megapixels'] = round((page_cv.shape[0] * page_cv.shape[1]) / 1000000, 1)
            page_result['dpi_used'] = high_dpi
            
            # Sauvegarder l'image de la page complète
            page_image_path = os.path.join(page_dir, "page_full_image.jpg")
            cv2.imwrite(page_image_path, page_cv)
            
            # Détecter les rectangles avec tous les détecteurs
            all_rectangles = []
            for detector in self.detectors:
                logger.info(f"    🔍 Détection avec {detector.name}")
                rectangles = detector.detect(page_cv)
                logger.info(f"      → {len(rectangles)} rectangles trouvés")
                
                # Ajouter les rectangles uniques avec filtre de taille pour Dubuffet
                for rect in rectangles:
                    if not self._is_duplicate_rectangle(rect, all_rectangles):
                        # Filtre spécifique Dubuffet : ignorer les petits rectangles
                        if self.collection.name.lower() == "dubuffet":
                            bbox = rect.get('bbox', {})
                            width = bbox.get('w', 0)
                            height = bbox.get('h', 0)
                            if width < 500 or height < 500:
                                logger.debug(f"    ⚠️ Rectangle ignoré (trop petit): {width}x{height}px")
                                continue
                        
                        all_rectangles.append(rect)
            
            page_result['rectangles_found'] = len(all_rectangles)
            logger.info(f"  🎯 TOTAL: {len(all_rectangles)} rectangles uniques détectés")
            
            # Créer dossier douteux
            doubtful_dir = FileUtils.create_doubtful_folder(page_dir)
            
            # Extraire et sauvegarder les images
            all_extracted_images = []
            all_rectangles_data = []
            
            # Première passe : extraire toutes les images
            for rect_idx, rectangle in enumerate(all_rectangles):
                try:
                    # Extraire l'image
                    extracted_image = self._extract_rectangle_image(page_cv, rectangle)
                    if extracted_image is None or not ImageUtils.is_image_valid(extracted_image):
                        continue
                    
                    all_extracted_images.append(extracted_image)
                    all_rectangles_data.append({
                        'image': extracted_image,
                        'rectangle': rectangle,
                        'rect_idx': rect_idx
                    })
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur rectangle {rect_idx + 1}: {e}")
                    continue
            
            # Analyser et classifier toutes les images
            for data in all_rectangles_data:
                try:
                    extracted_image = data['image']
                    rectangle = data['rectangle']
                    rect_idx = data['rect_idx']
                    
                    # Analyser la qualité
                    quality_analysis = self.quality_analyzer.analyze_image_quality(
                        extracted_image, 
                        all_extracted_images
                    )
                    
                    # Détecter numéro d'œuvre
                    artwork_number = self._detect_artwork_number(page_cv, rectangle)
                    
                    # Déterminer le nom et le dossier
                    if artwork_number:
                        base_filename = f"{artwork_number}.png"
                    else:
                        base_filename = f"rectangle_{rect_idx + 1:02d}.png"
                    
                    # Décider où sauvegarder
                    if quality_analysis['is_doubtful']:
                        filename = f"DOUTEUX_{base_filename}"
                        image_path = os.path.join(doubtful_dir, filename)
                        
                        # Créer un fichier info
                        self._create_doubtful_info(doubtful_dir, base_filename, 
                                                 quality_analysis, extracted_image)
                        
                        logger.info(f"    ⚠️ Sauvé (DOUTEUX): {filename}")
                    else:
                        filename = base_filename
                        image_path = os.path.join(page_dir, filename)
                        logger.info(f"    ✅ Sauvé: {filename} ({extracted_image.shape[1]}×{extracted_image.shape[0]})")
                    
                    # Créer miniature
                    thumbnail = ImageUtils.create_thumbnail(extracted_image)
                    thumb_path = os.path.join(os.path.dirname(image_path), f"thumb_{filename}")
                    cv2.imwrite(thumb_path, thumbnail)
                    
                    # Sauvegarder l'image
                    cv2.imwrite(image_path, extracted_image)
                    
                    # NOUVEAU : Créer le JSON d'œuvre immédiatement
                    # PICASSO : Utilise le sommaire (plate_map)
                    # DUBUFFET : Utilise l'OCR immédiat des légendes
                    
                    if hasattr(self, 'plate_map') and self.plate_map and artwork_number:
                        # PICASSO - JSON via sommaire
                        try:
                            from toc_planches import create_artwork_json, save_artwork_json, extract_artist_name_from_pdf
                            
                            plate_number = int(artwork_number)
                            logger.debug(f"🔍 Tentative création JSON pour planche {plate_number}")
                            logger.debug(f"🔍 Planches disponibles: {list(self.plate_map.keys())[:10]}...")
                            
                            if plate_number in self.plate_map:
                                # Obtenir le nom de l'artiste (une seule fois)
                                if not hasattr(self, 'artist_name'):
                                    self.artist_name = extract_artist_name_from_pdf(self.current_pdf_path)
                                
                                # Créer le JSON de l'œuvre
                                plate_info = self.plate_map[plate_number]
                                logger.info(f"🔍 Plate info pour {plate_number}: {plate_info}")
                                image_size = (extracted_image.shape[1], extracted_image.shape[0])
                                logger.info(f"🔍 Appel create_artwork_json pour planche {plate_number}")
                                artwork_data = create_artwork_json(
                                    image_path, plate_number, plate_info, self.artist_name, image_size
                                )
                                logger.info(f"🔍 JSON créé avec medium: {artwork_data.get('medium', 'N/A')}")
                                
                                # Sauvegarder le JSON
                                from pathlib import Path
                                json_path = save_artwork_json(artwork_data, Path(page_dir), plate_number)
                                if json_path:
                                    logger.info(f"    🎨 JSON créé: oeuvre_{plate_number:03d}.json")
                            else:
                                logger.warning(f"    ⚠️ Planche {plate_number} non trouvée dans le sommaire")
                        except Exception as e:
                            logger.error(f"❌ Erreur création JSON immédiat: {e}")
                            import traceback
                            logger.debug(f"Traceback: {traceback.format_exc()}")
                    
                    elif self.collection.name.lower() == "dubuffet" and artwork_number:
                        # DUBUFFET - JSON via OCR immédiat des légendes
                        try:
                            logger.info(f"🎨 OCR immédiat Dubuffet pour image {artwork_number}")
                            from dubuffet_ocr_extractor import DubuffetOCRExtractor
                            
                            # Initialiser l'extracteur OCR
                            if not hasattr(self, 'dubuffet_ocr'):
                                self.dubuffet_ocr = DubuffetOCRExtractor()
                            
                            # Charger l'image de la page complète
                            page_full_path = os.path.join(page_dir, "page_full_image.jpg")
                            if os.path.exists(page_full_path):
                                page_bgr = cv2.imread(page_full_path)
                                
                                # Utiliser la bbox de l'image détectée comme zone d'œuvre
                                bbox = rectangle.get('bbox', {})
                                artwork_bbox = (
                                    bbox.get('x', 0), bbox.get('y', 0),
                                    bbox.get('x', 0) + bbox.get('w', 0),
                                    bbox.get('y', 0) + bbox.get('h', 0)
                                ) if bbox else None
                                
                                # Extraire la légende pour cette œuvre (avec bandes réduites)
                                debug_prefix = os.path.join(page_dir, f"ocr_debug_artwork_{artwork_number}")
                                caption_result = self.dubuffet_ocr.extract_caption_from_page(
                                    page_bgr, artwork_bbox, band_px=150, save_debug=True, debug_prefix=debug_prefix
                                )
                                
                                if caption_result.get("found_caption") and caption_result.get("items"):
                                    # Prendre la première légende trouvée
                                    caption_data = caption_result["items"][0]
                                    
                                    # Créer le JSON d'œuvre Dubuffet
                                    artwork_num = int(artwork_number) if str(artwork_number).isdigit() else 0
                                    artwork_json = {
                                        "id": f"artwork_{artwork_num:03d}",
                                        "index": caption_data.get("index", artwork_num),
                                        "title": caption_data.get("title"),
                                        "medium": caption_data.get("medium"),
                                        "dimensions_cm": caption_data.get("dimensions_cm", {"width": None, "height": None}),
                                        "date_text": caption_data.get("date_text"),
                                        "date_iso": caption_data.get("date_iso"),
                                        "approximate": caption_data.get("approximate", False),
                                        "page": page_num,
                                        "image_file": filename,
                                        "image_path": image_path,
                                        "image_size": {"width": extracted_image.shape[1], "height": extracted_image.shape[0]},
                                        "ocr_region": caption_data.get("region"),
                                        "ocr_confidence": caption_data.get("confidence_mean", 0.0),
                                        "ocr_text_raw": caption_data.get("ocr_text_raw", ""),
                                        "extraction_method": "dubuffet_immediate_ocr",
                                        "extraction_date": datetime.now().isoformat()
                                    }
                                    
                                    # Sauvegarder le JSON individuel
                                    json_filename = f"oeuvre_{artwork_num:03d}.json"
                                    json_path = os.path.join(page_dir, json_filename)
                                    with open(json_path, 'w', encoding='utf-8') as f:
                                        json.dump(artwork_json, f, indent=2, ensure_ascii=False)
                                    
                                    logger.info(f"    🎨 JSON Dubuffet créé: {json_filename}")
                                    logger.info(f"    📝 Titre: {caption_data.get('title', 'N/A')}")
                                    logger.info(f"    🎭 Médium: {caption_data.get('medium', 'N/A')}")
                                else:
                                    logger.warning(f"    ⚠️ Aucune légende trouvée pour l'œuvre {artwork_number}")
                            else:
                                logger.warning(f"    ⚠️ Image de page complète non trouvée: {page_full_path}")
                                
                        except Exception as e:
                            logger.error(f"❌ Erreur OCR immédiat Dubuffet: {e}")
                            import traceback
                            logger.debug(f"Traceback: {traceback.format_exc()}")
                    
                    # Enregistrer les détails
                    rect_details = {
                        'rectangle_id': rect_idx + 1,
                        'filename': filename,
                        'is_doubtful': quality_analysis['is_doubtful'],
                        'confidence': quality_analysis['confidence'],
                        'doubt_reasons': quality_analysis['reasons'],
                        'artwork_number': artwork_number,
                        'bbox': rectangle.get('bbox'),
                        'area': rectangle.get('area'),
                        'size_kb': FileUtils.get_file_size_kb(image_path),
                        'thumbnail': f"thumb_{filename}",
                        'detection_method': rectangle.get('method', 'unknown'),
                        'original_confidence': rectangle.get('confidence', 0.5)
                    }
                    
                    page_result['rectangles_details'].append(rect_details)
                    page_result['images_saved'].append(filename)
                    page_result['images_extracted'] += 1
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur sauvegarde {rect_idx + 1}: {e}")
                    continue
            
            # Analyser la cohérence des numéros
            logger.info(f"  🔍 Analyse de cohérence des numéros...")
            coherence_result = self.coherence_analyzer.analyze(page_result['rectangles_details'])
            page_result['coherence_analysis'] = coherence_result
            
            # NOUVEAU : Détecter et analyser les sommaires
            logger.info(f"  📋 Vérification du sommaire...")
            page_result = self.analyze_summary_page(page_result, page_cv)
            
            # Afficher les résultats de cohérence
            if 'error' not in coherence_result:
                detected = coherence_result.get('detected_numbers', [])
                is_seq = coherence_result.get('is_sequential', True)
                gaps = coherence_result.get('gaps', [])
                
                if is_seq:
                    logger.info(f"  ✅ Numéros cohérents: {detected}")
                else:
                    logger.warning(f"  ⚠️ Incohérences détectées: {detected}")
                    if gaps:
                        logger.warning(f"  🔍 Numéros manquants: {gaps}")
            
            page_result['success'] = True
            
        except Exception as e:
            logger.error(f"  ❌ Erreur page {page_num}: {e}")
            page_result['error'] = str(e)
        
        # Calculer le temps de traitement
        page_result['processing_time'] = round(time.time() - page_start_time, 2)
        page_result['end_time'] = datetime.now().isoformat()
        
        # Sauvegarder le log de la page
        page_log_path = os.path.join(page_dir, "page_ultra_details.json")
        with open(page_log_path, 'w', encoding='utf-8') as f:
            json.dump(page_result, f, indent=2, ensure_ascii=False)
        
        # Créer le fichier texte de détails
        self._create_page_text_details(page_dir, page_result)
        
        return page_result
    
    def _analyze_page_dimensions(self, pdf_path: str, page_number: int) -> dict:
        """Analyse les dimensions d'une page"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page = pdf_reader.pages[page_number - 1]
                
                mediabox = page.mediabox
                width_points = float(mediabox.width)
                height_points = float(mediabox.height)
                
                width_mm = width_points * 25.4 / 72
                height_mm = height_points * 25.4 / 72
                area_mm2 = width_mm * height_mm
                
                page_format = self._identify_page_format(width_mm, height_mm)
                recommended_dpi = self._calculate_optimal_dpi(width_mm, height_mm, area_mm2)
                
                return {
                    'width_mm': round(width_mm, 1),
                    'height_mm': round(height_mm, 1),
                    'area_mm2': round(area_mm2, 0),
                    'page_format': page_format,
                    'recommended_dpi': recommended_dpi
                }
        except:
            return {
                'width_mm': 210.0,
                'height_mm': 297.0,
                'area_mm2': 62370,
                'page_format': 'A4 (défaut)',
                'recommended_dpi': 400
            }
    
    def _identify_page_format(self, width_mm: float, height_mm: float) -> str:
        """Identifie le format de page"""
        w, h = sorted([width_mm, height_mm])
        
        formats = {
            (148, 210): "A5", 
            (210, 297): "A4",
            (297, 420): "A3",
            (216, 279): "Letter US",
        }
        
        for (fw, fh), format_name in formats.items():
            if abs(w - fw) <= 5 and abs(h - fh) <= 5:
                return format_name
        
        return f"Personnalisé {w:.0f}×{h:.0f}mm"
    
    def _calculate_optimal_dpi(self, width_mm: float, height_mm: float, area_mm2: float) -> int:
        """Calcule le DPI optimal"""
        if area_mm2 < 30000:  # < A5
            return 500
        elif area_mm2 < 70000:  # A5-A4
            return 400
        elif area_mm2 < 150000:  # A4-A3
            return 350
        else:  # > A3
            return 300
    
    def _extract_rectangle_image(self, image: np.ndarray, rectangle: dict) -> np.ndarray:
        """Extrait l'image d'un rectangle"""
        try:
            bbox = rectangle['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # Extraction simple uniquement
            bbox_image = image[y:y+h, x:x+w].copy()
            return bbox_image
            
        except Exception as e:
            logger.error(f"Erreur extraction rectangle: {e}")
            return None
    
    def analyze_summary_page(self, page_result: dict, page_image: np.ndarray) -> dict:
        """Analyse si la page contient un sommaire et extrait les informations d'œuvres"""
        try:
            # Extraire le texte de la page avec OCR
            page_text = self._extract_page_text(page_image)
            
            if not page_text or len(page_text.strip()) < 50:
                page_result['summary_analysis'] = {
                    'is_summary': False,
                    'message': 'Pas assez de texte pour analyser'
                }
                return page_result
            
            # Analyser avec l'analyseur de sommaires
            summary_analysis = self.summary_analyzer.analyze_summary_page(page_text, page_image)
            
            # Sauvegarder l'analyse si c'est un sommaire
            if summary_analysis.get('is_summary'):
                page_dir = page_result.get('page_dir', '')
                summary_file = os.path.join(page_dir, "summary_analysis.json")
                self.summary_analyzer.save_summary_analysis(summary_analysis, summary_file)
                
                logger.info(f"  📋 Sommaire détecté: {summary_analysis.get('total_entries', 0)} entrées d'œuvres")
            
            page_result['summary_analysis'] = summary_analysis
            return page_result
            
        except Exception as e:
            logger.error(f"  ❌ Erreur analyse sommaire: {e}")
            page_result['summary_analysis'] = {
                'is_summary': False,
                'error': str(e)
            }
            return page_result
    
    def _extract_page_text(self, page_image: np.ndarray) -> str:
        """Extrait le texte d'une page avec OCR"""
        try:
            import pytesseract
            
            # Vérifier Tesseract avec test de version
            try:
                _ = pytesseract.get_tesseract_version()
            except Exception:
                return ""
            
            # Convertir en niveaux de gris
            gray = cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
            
            # Prétraitement pour améliorer l'OCR
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # OCR avec plusieurs configurations
            text = pytesseract.image_to_string(enhanced, config='--psm 6')
            
            return text.strip()
            
        except Exception as e:
            logger.debug(f"Erreur OCR: {e}")
            return ""
    
    def _detect_artwork_number(self, image: np.ndarray, rectangle: dict) -> str:
        """Détecte le numéro d'œuvre selon la collection configurée"""
        try:
            import pytesseract
            import re
            
            # Vérifier Tesseract
            try:
                _ = pytesseract.get_tesseract_version()
            except Exception:
                return None
            
            # Obtenir les zones de détection depuis la collection
            zones = self.collection.get_detection_zones(image, rectangle)
            if not zones:
                return None
            
            # Configuration OCR de la collection
            ocr_config = self.collection.get_ocr_config()
            scoring_weights = self.collection.get_scoring_weights()
            
            # Prétraitements
            def apply_preprocessing(gray, preprocessing_list):
                results = []
                for prep_type in preprocessing_list:
                    if prep_type == 'otsu':
                        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        results.append(b)
                    elif prep_type == 'otsu_inv':
                        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                        results.append(b)
                    elif prep_type == 'adaptive':
                        b = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 9)
                        results.append(b)
                    elif prep_type == 'clahe_otsu':
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                g2 = clahe.apply(gray)
                        _, b = cv2.threshold(g2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        results.append(b)
                    elif prep_type == 'gaussian_blur_otsu':
                        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
                        _, b = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        results.append(b)
                return results

            best = (None, 0.0)
            zone_weights = scoring_weights.get('zone_weights', [1.0] * len(zones))
            length_bonus = scoring_weights.get('length_bonus', {1: 1.0, 2: 1.0, 3: 1.0})
            early_stop_threshold = scoring_weights.get('early_stop_threshold', 8.0)
            
            # Parcourir les zones par priorité
            for zone_idx, (sx, sy, sw, sh) in enumerate(zones):
                if sw <= 5 or sh <= 5:
                    continue
                    
                roi = image[sy:sy+sh, sx:sx+sw]
                if roi.size == 0:
                    continue
                    
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
                
                # Appliquer les prétraitements de la collection
                preprocessed_images = apply_preprocessing(gray, ocr_config.get('preprocessing', ['otsu']))
                
                for processed_img in preprocessed_images:
                    # Agrandir pour OCR
                    scale_factor = ocr_config.get('scale_factor', 3.0)
                    big = cv2.resize(processed_img, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
                    
                    # Tester chaque configuration OCR avec timeout
                    for psm_config in ocr_config.get('psm_configs', ['--psm 7 -c tessedit_char_whitelist=0123456789']):
                        try:
                            # Ajouter un timeout pour éviter les blocages sur les vieux PC
                            import signal
                            import threading
                            
                            def timeout_handler():
                                return None
                            
                            # OCR avec timeout de 10 secondes max
                            ocr_result = None
                            def run_ocr():
                                nonlocal ocr_result
                                try:
                                    ocr_result = pytesseract.image_to_string(big, config=psm_config, timeout=10)
                                except Exception as e:
                                    logger.debug(f"OCR timeout ou erreur: {e}")
                                    ocr_result = None
                            
                            ocr_thread = threading.Thread(target=run_ocr)
                            ocr_thread.daemon = True
                            ocr_thread.start()
                            ocr_thread.join(timeout=15)  # 15 secondes max total
                            
                            if ocr_thread.is_alive():
                                logger.debug(f"⚠️ OCR timeout après 15s, passage au suivant")
                                continue
                            
                            if not ocr_result:
                                continue
                                
                            text = ocr_result
                            match = re.search(r"\b\d{1,6}\b", text)
                            if match:
                                raw_number = match.group(0)
                                
                                # Utiliser le préprocessing de la collection
                                processed_number = self.collection.preprocess_number(raw_number)
                                if not processed_number:
                                    continue
                                
                                # Calcul du score avec les poids de la collection
                                zone_weight = zone_weights[zone_idx] if zone_idx < len(zone_weights) else 1.0
                                length_weight = length_bonus.get(len(processed_number), 1.0)
                                
                                score = zone_weight * length_weight
                            
                            if score > best[1]:
                                    best = (processed_number, score)
                                    logger.debug(f"✅ Nouveau meilleur score: {processed_number} (score: {score:.2f})")
                                
                        except Exception as e:
                            logger.debug(f"Erreur OCR: {e}")
                        continue

                # Arrêt précoce selon le seuil de la collection
                if best[0] and best[1] >= early_stop_threshold and zone_idx <= 1:
                    break

            return best[0]
        except Exception as e:
            logger.debug(f"Erreur détection numéro: {e}")
            return None
    
    def _is_duplicate_rectangle(self, new_rect: dict, existing_rects: list) -> bool:
        """Vérifie si un rectangle est un doublon"""
        # Implémentation directe de la logique de déduplication
        new_bbox = new_rect['bbox']
        new_x, new_y = new_bbox['x'], new_bbox['y']
        new_w, new_h = new_bbox['w'], new_bbox['h']
        
        for existing_rect in existing_rects:
            ex_bbox = existing_rect['bbox']
            ex_x, ex_y = ex_bbox['x'], ex_bbox['y']
            ex_w, ex_h = ex_bbox['w'], ex_bbox['h']
            
            # Calculer le centre de chaque rectangle
            new_center = (new_x + new_w/2, new_y + new_h/2)
            ex_center = (ex_x + ex_w/2, ex_y + ex_h/2)
            
            # Distance entre les centres
            center_distance = np.sqrt((new_center[0] - ex_center[0])**2 + 
                                     (new_center[1] - ex_center[1])**2)
            
            # Si les centres sont très proches ET les tailles similaires
            max_dim = max(new_w, new_h, ex_w, ex_h)
            if center_distance < max_dim * 0.15:
                # Vérifier aussi la similarité des tailles
                size_ratio_w = min(new_w, ex_w) / max(new_w, ex_w)
                size_ratio_h = min(new_h, ex_h) / max(new_h, ex_h)
                
                if size_ratio_w > 0.8 and size_ratio_h > 0.8:
                    return True
            
            # Fallback: méthode de chevauchement classique
            left = max(new_x, ex_x)
            top = max(new_y, ex_y)
            right = min(new_x + new_w, ex_x + ex_w)
            bottom = min(new_y + new_h, ex_y + ex_h)
            
            if left < right and top < bottom:
                intersection = (right - left) * (bottom - top)
                area1 = new_w * new_h
                area2 = ex_w * ex_h
                
                # Si plus de 70% de chevauchement, c'est un doublon
                overlap_ratio = intersection / min(area1, area2)
                if overlap_ratio > 0.7:
                    return True
        
        return False
    
    def _create_doubtful_info(self, doubtful_dir: str, base_filename: str, 
                             quality_analysis: dict, extracted_image: np.ndarray):
        """Crée un fichier info pour une image douteuse"""
        info_filename = f"{base_filename.replace('.png', '_INFO.txt')}"
        info_path = os.path.join(doubtful_dir, info_filename)
        
        with open(info_path, 'w', encoding='utf-8') as f:
            f.write(f"IMAGE DOUTEUSE - ANALYSE AUTOMATIQUE\n")
            f.write(f"={'=' * 40}\n\n")
            f.write(f"Fichier: {base_filename}\n")
            f.write(f"Confiance: {quality_analysis['confidence']:.2f}/1.0\n")
            f.write(f"Dimensions: {extracted_image.shape[1]}×{extracted_image.shape[0]} pixels\n")
            f.write(f"Taille: {(extracted_image.shape[0] * extracted_image.shape[1]) // 1000}K pixels\n\n")
            f.write(f"RAISONS DE LA CLASSIFICATION DOUTEUSE:\n")
            for reason in quality_analysis['reasons']:
                desc = self.quality_analyzer.get_quality_description(reason)
                f.write(f"{desc}\n")
    
    def _create_page_text_details(self, page_dir: str, page_result: dict):
        """Crée un fichier texte avec les détails de la page"""
        details_path = os.path.join(page_dir, "README_ULTRA.txt")
        
        content = f"""PAGE {page_result['page_number']} - EXTRACTION ULTRA SENSIBLE
{'=' * 60}

MODE: ULTRA SENSIBLE - Capture TOUT !
- Statut: {'✅ Succès' if page_result['success'] else '❌ Échec'}
- Temps de traitement: {page_result['processing_time']}s
- Images extraites: {page_result['images_extracted']}
- Rectangles détectés: {page_result['rectangles_found']}
- DPI utilisé: {page_result.get('dpi_used', 'N/A')}

ANALYSE DE PAGE:
- Format: {page_result.get('page_analysis', {}).get('page_format', 'N/A')}
- Taille physique: {page_result.get('page_analysis', {}).get('width_mm', 0):.1f}×{page_result.get('page_analysis', {}).get('height_mm', 0):.1f}mm
- Taille image: {page_result.get('image_size', 'N/A')}
- Mégapixels: {page_result.get('image_megapixels', 0)}MP

IMAGES EXTRAITES:
"""
        
        if page_result['images_saved']:
            for i, img_name in enumerate(page_result['images_saved'], 1):
                details = next((r for r in page_result.get('rectangles_details', []) 
                              if r['filename'] == img_name), {})
                
                content += f"""
{i:2d}. {img_name}
    - Numéro d'œuvre: {details.get('artwork_number', 'Aucun')}
    - Taille: {details.get('size_kb', 0)} KB
    - Méthode détection: {details.get('detection_method', 'N/A')}
    - Confiance: {details.get('confidence', 0):.2f}
    - Miniature: {details.get('thumbnail', 'N/A')}
"""
        else:
            content += "\nAucune image extraite (page vide ou erreur).\n"
        
        if page_result.get('error'):
            content += f"\nERREUR:\n{page_result['error']}\n"
        
        content += f"""
Extraction ULTRA effectuée le {page_result.get('start_time', 'N/A')}
"""
        
        with open(details_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_text_summary(self, global_log: dict):
        """Crée un résumé texte global"""
        summary_path = os.path.join(self.session_dir, "RÉSUMÉ_ULTRA.txt")
        
        content = f"""EXTRACTION PDF ULTRA SENSIBLE - RÉSUMÉ COMPLET
{'=' * 70}

🎯 MODE ULTRA SENSIBLE - CAPTURE TOUT !

FICHIER SOURCE:
- Nom: {global_log['pdf_name']}
- Chemin: {global_log['pdf_path']}

EXTRACTION ULTRA:
- Début: {global_log['start_time']}
- Fin: {global_log['end_time']}

RÉSULTATS ULTRA:
- Pages traitées: {global_log['total_pages']}
- Pages réussies: {global_log['success_pages']}
- Pages échouées: {global_log['failed_pages']}
- Images extraites: {global_log['total_images_extracted']} ⚡ ULTRA SENSIBLE

🎉 RÉSULTAT: {global_log['total_images_extracted']} images extraites avec le mode ULTRA !
   Aucune image ne devrait être ratée avec cette méthode.
"""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(content)
