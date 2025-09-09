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

class PDFExtractor:
    """Extracteur PDF principal avec architecture modulaire"""
    
    def __init__(self):
        self.output_base_dir = OUTPUT_BASE_DIR
        self.session_dir = None
        self.total_extracted = 0
        
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
        try:
            logger.info("🔍 Recherche TABLE DES PLANCHES dans les 15 dernières pages...")
            toc_data = extract_toc_from_pdf_multipage(pdf_path, last_n=15)
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
                
                # Ajouter les rectangles uniques
                for rect in rectangles:
                    if not self._is_duplicate_rectangle(rect, all_rectangles):
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
                    
                    # NOUVEAU : Créer le JSON d'œuvre immédiatement si on a le sommaire
                    if hasattr(self, 'plate_map') and self.plate_map and artwork_number:
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
        """Détecte le numéro d'œuvre sous/près du visuel.
        Heuristiques:
        - Zones de recherche par priorité stricte
        - OCR optimisé pour nombres courts (1-6 chiffres)
        - Prétraitements multiples pour robustesse
        Retourne une chaîne du numéro ou None.
        """
        try:
            import pytesseract
            import re
            
            # Vérifier Tesseract avec test de version
            try:
                _ = pytesseract.get_tesseract_version()
            except Exception:
                return None
            
            H, W = image.shape[:2]
            bbox = rectangle.get('bbox', {})
            x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)

            # Définir zones de recherche (clamp aux bords)
            def clamp_zone(zx, zy, zw, zh):
                zx = max(0, zx); zy = max(0, zy)
                zw = max(0, min(zw, W - zx))
                zh = max(0, min(zh, H - zy))
                return (zx, zy, zw, zh)

            # Zones de recherche par priorité stricte
            pad_x = max(10, w // 20)
            pad_y = max(10, h // 20)

            zones = [
                # PRIORITÉ 1: Petite bande sous l'image (30-80px)
                clamp_zone(x - pad_x, y + h + 2, w + 2 * pad_x, max(30, min(80, h // 3))),
                # PRIORITÉ 2: Bande plus large sous l'image (40-100px)
                clamp_zone(x - pad_x*2, y + h + 2, w + 4 * pad_x, max(40, min(100, h // 2))),
                # PRIORITÉ 3: Très fine bande DANS l'image - bas (20px)
                clamp_zone(x + w//6, y + h - 20, w*2//3, 20),
                # PRIORITÉ 4: Très fine bande DANS l'image - haut (20px)
                clamp_zone(x + w//6, y, w*2//3, 20),
                # PRIORITÉ 5: Zone à droite de l'image
                clamp_zone(x + w + 4, y, min(80 + w // 3, W - (x + w + 4)), min(h, 120)),
                # PRIORITÉ 6: Zone à gauche de l'image
                clamp_zone(max(0, x - (60 + w // 3)), y, min(80 + w // 3, x), min(h, 120)),
            ]

            # Prétraitements à tester
            def prepro(gray):
                outs = []
                # OTSU
                _, b1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                outs.append(b1)
                # OTSU inversé
                _, b2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                outs.append(b2)
                # Adaptatif
                b3 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 9)
                outs.append(b3)
                # CLAHE puis OTSU
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                g2 = clahe.apply(gray)
                _, b4 = cv2.threshold(g2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                outs.append(b4)
                return outs

            # OCR optimisé pour nombres courts (1-6 chiffres)
            def extract_numbers_optimized(text):
                """Extrait les nombres de 1-6 chiffres avec regex simple"""
                text_norm = text.replace('\n', ' ').strip()
                candidates = []
                
                # Chercher nombres de 1-6 chiffres
                for m in re.finditer(r'\b(\d{1,6})\b', text_norm):
                    num = m.group(1)
                    # Éviter années probables (4 chiffres > 1899)
                    if len(num) == 4 and int(num) > 1899:
                        continue
                    # Priorité aux nombres courts (1-3 chiffres)
                    weight = 2.0 if len(num) <= 3 else 1.0
                    candidates.append((num, weight))
                
                return candidates

            best = (None, 0.0)
            # Parcourir les zones (priorité stricte)
            for zone_idx, (sx, sy, sw, sh) in enumerate(zones):
                if sw <= 5 or sh <= 5:
                    continue
                roi = image[sy:sy+sh, sx:sx+sw]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                
                for b in prepro(gray):
                    # Agrandir pour OCR
                    big = cv2.resize(b, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                    
                    # OCR optimisé pour nombres courts
                    try:
                        config = "--psm 7 -c tessedit_char_whitelist=0123456789"
                        text = pytesseract.image_to_string(big, config=config)
                        match = re.search(r"\b\d{1,6}\b", text)
                        if match:
                            num = match.group(0)
                            # Éviter années probables
                            if len(num) == 4 and int(num) > 1899:
                                continue
                            
                            # Scoring hiérarchique par zone
                            if zone_idx == 0:  # Petite bande sous l'image (priorité maximale)
                                proximity = 4.0
                                zone_bonus = 3.0
                            elif zone_idx == 1:  # Bande plus large sous l'image
                                proximity = 3.5
                                zone_bonus = 2.5
                            elif zone_idx == 2:  # Fine bande DANS l'image - bas
                                proximity = 3.0
                                zone_bonus = 2.0
                            elif zone_idx == 3:  # Fine bande DANS l'image - haut
                                proximity = 2.5
                                zone_bonus = 1.8
                            elif zone_idx == 4:  # À droite
                                proximity = 1.5
                                zone_bonus = 1.2
                            else:  # À gauche
                                proximity = 1.5
                                zone_bonus = 1.2
                            
                            # Bonus pour nombres courts
                            length_bonus = 2.0 if len(num) <= 3 else 1.0
                            
                            # Vérifier distance horizontale (sauf zones latérales)
                            center_x = sx + sw // 2
                            rect_center_x = x + w // 2
                            horizontal_distance = abs(center_x - rect_center_x)
                            
                            if zone_idx < 4 and horizontal_distance > w * 0.8:
                                continue
                            
                            score = proximity * zone_bonus * length_bonus
                            
                            if score > best[1]:
                                best = (num, score)
                                
                    except Exception:
                        continue

                # Arrêt précoce si très bon score dans zones prioritaires
                if best[0] and best[1] >= 8.0 and zone_idx <= 1:
                    break

            return best[0]
        except Exception:
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
