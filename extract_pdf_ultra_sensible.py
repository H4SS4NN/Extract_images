#!/usr/bin/env python3
"""
Script d'extraction PDF ULTRA SENSIBLE - Capture TOUT !
Ne rate aucune image, même les plus petites ou peu contrastées
"""

import os
import cv2
import numpy as np
import json
import time
import re
import logging
from datetime import datetime
from pathlib import Path
from pdf2image import convert_from_path
import PyPDF2
import pytesseract
import requests
import base64
from io import BytesIO
import pdfplumber

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UltraSensitivePDFExtractor:
    def __init__(self):
        self.output_base_dir = "extractions_ultra"
        self.session_dir = None
        self.total_extracted = 0
        
        # Configuration Tesseract
        self._configure_tesseract()
        
        # Configuration Ollama
        self.ollama_url = "http://localhost:11434/api/generate"
        self.ollama_model = "llava"  # Modèle vision + texte
        self.ollama_enabled = self._check_ollama_availability()
        
        # Tester LLaVA si disponible
        if self.ollama_enabled:
            self._test_llava_capabilities()
    
    def _configure_tesseract(self):
        """Configure Tesseract OCR"""
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe", 
            r"C:\Users\lburg\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            r"C:\tesseract\tesseract.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"✅ Tesseract trouvé: {path}")
                return True
        
        logger.warning("⚠️ Tesseract non trouvé - OCR désactivé")
        return False
    
    def _check_ollama_availability(self):
        """Vérifie si Ollama est disponible avec LLaVA"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                
                # Chercher LLaVA (peut être llava, llava:latest, llava:7b, etc.)
                llava_models = [name for name in model_names if 'llava' in name.lower()]
                
                if llava_models:
                    # Prendre le premier modèle LLaVA trouvé
                    self.ollama_model = llava_models[0]
                    logger.info(f"✅ Ollama disponible avec modèle LLaVA: {self.ollama_model}")
                    logger.info("🔍 LLaVA peut analyser les images et détecter les numéros d'œuvres")
                    return True
                else:
                    logger.warning("⚠️ Ollama disponible mais modèle LLaVA non trouvé")
                    logger.warning("💡 Pour installer LLaVA: ollama pull llava")
                    return False
        except Exception as e:
            logger.warning(f"⚠️ Ollama non disponible: {e}")
            logger.warning("💡 Pour installer Ollama: https://ollama.ai/")
            return False
    
    def _query_ollama_vision(self, image, prompt):
        """Interroge le modèle LLaVA avec une image"""
        if not self.ollama_enabled:
            return None
        
        try:
            # Redimensionner l'image si elle est trop grande (LLaVA a des limites)
            height, width = image.shape[:2]
            max_size = 1024
            
            if max(height, width) > max_size:
                scale = max_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
                logger.debug(f"    🔍 Image redimensionnée pour LLaVA: {width}×{height} → {new_width}×{new_height}")
            
            # Convertir l'image en base64
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Plus déterministe pour l'analyse
                    "top_p": 0.9,
                    "max_tokens": 300,  # Réduit pour éviter les timeouts
                    "num_ctx": 2048,    # Contexte réduit
                    "num_predict": 200  # Limite de tokens
                }
            }
            
            logger.debug(f"    🤖 Envoi requête LLaVA: {prompt[:100]}...")
            # Timeout plus long pour LLaVA mais avec retry
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                logger.debug(f"    🤖 Réponse LLaVA: {response_text}")
                return response_text
            else:
                logger.error(f"    ❌ Erreur Ollama {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning("    ⚠️ Timeout LLaVA - essai avec prompt simplifié...")
            # Essayer avec un prompt plus simple
            return self._query_ollama_simple(image, prompt)
        except Exception as e:
            logger.error(f"    ❌ Erreur requête Ollama: {e}")
            return None
    
    def _query_ollama_simple(self, image, original_prompt):
        """Version simplifiée pour éviter les timeouts"""
        try:
            # Redimensionner encore plus pour aller plus vite
            height, width = image.shape[:2]
            max_size = 512  # Plus petit
            
            if max(height, width) > max_size:
                scale = max_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Convertir l'image en base64
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Prompt très simple
            simple_prompt = "Liste tous les numéros visibles dans cette image. Réponds juste les numéros séparés par des virgules."
            
            payload = {
                "model": self.ollama_model,
                "prompt": simple_prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "max_tokens": 100,  # Très court
                    "num_ctx": 1024,   # Contexte minimal
                    "num_predict": 50  # Très limité
                }
            }
            
            logger.debug(f"    🤖 Envoi requête LLaVA simplifiée...")
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                logger.debug(f"    🤖 Réponse LLaVA simplifiée: {response_text}")
                return response_text
            else:
                logger.error(f"    ❌ Erreur LLaVA simplifiée: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"    ❌ Erreur LLaVA simplifiée: {e}")
            return None
    
    def _test_llava_capabilities(self):
        """Teste les capacités de LLaVA avec une image simple"""
        try:
            # Créer une image de test simple
            test_image = np.ones((200, 400, 3), dtype=np.uint8) * 255  # Image blanche
            cv2.putText(test_image, "Test 123", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
            
            prompt = "Peux-tu voir le texte 'Test 123' dans cette image ? Réponds simplement OUI ou NON."
            
            logger.info("🧪 Test des capacités LLaVA...")
            response = self._query_ollama_vision(test_image, prompt)
            
            if response and 'OUI' in response.upper():
                logger.info("✅ LLaVA fonctionne correctement - vision activée")
            elif response and 'NON' in response.upper():
                logger.warning("⚠️ LLaVA répond mais ne voit pas le texte - problème de vision")
            elif response:
                logger.warning(f"⚠️ LLaVA répond mais de manière inattendue: {response}")
            else:
                logger.warning("⚠️ LLaVA ne répond pas - peut être trop lent")
                logger.info("💡 LLaVA sera désactivé pour cette session")
                self.ollama_enabled = False
                
        except Exception as e:
            logger.warning(f"⚠️ Test LLaVA échoué: {e}")
            logger.info("💡 LLaVA sera désactivé pour cette session")
            self.ollama_enabled = False
    
    def create_session_folder(self, pdf_name):
        """Crée le dossier de session principal"""
        clean_name = os.path.splitext(pdf_name)[0]
        clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = f"{clean_name}_ULTRA_{timestamp}"
        
        self.session_dir = os.path.join(self.output_base_dir, session_name)
        os.makedirs(self.session_dir, exist_ok=True)
        
        logger.info(f"📁 Session ULTRA créée: {self.session_dir}")
        return self.session_dir
    
    def create_page_folder(self, page_num):
        """Crée un dossier pour une page spécifique"""
        page_dir = os.path.join(self.session_dir, f"page_{page_num:03d}")
        os.makedirs(page_dir, exist_ok=True)
        return page_dir
    
    def extract_pdf(self, pdf_path, max_pages=None, start_page=1):
        """Extraction complète ULTRA SENSIBLE d'un PDF
        start_page: numéro de page 1-indexé à partir duquel commencer
        max_pages: nombre max de pages à traiter (None = jusqu'à la fin)
        """
        if not os.path.exists(pdf_path):
            logger.error(f"❌ Fichier non trouvé: {pdf_path}")
            return False
        
        logger.info(f"🚀 EXTRACTION ULTRA SENSIBLE: {os.path.basename(pdf_path)}")
        logger.info("🎯 MODE ULTRA: Capture TOUT, même les plus petites images !")
        
        # Créer la session
        pdf_name = os.path.basename(pdf_path)
        self.create_session_folder(pdf_name)
        
        # Compter les pages
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pdf_pages = len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"❌ Impossible de lire le PDF: {e}")
            return False
        
        # Valider la page de départ
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
        
        # Créer le fichier de résumé global
        global_log = {
            'pdf_name': pdf_name,
            'pdf_path': os.path.abspath(pdf_path),  # Chemin absolu pour retrouver le PDF
            'pdf_original_path': os.path.abspath(pdf_path),  # Sauvegarde du chemin original
            'session_dir': self.session_dir,
            'mode': 'ULTRA_SENSIBLE',
            'start_time': datetime.now().isoformat(),
            'total_pages': total_pages,
            'start_page': start_page,
            'end_page': end_page,
            'pages': []
        }
        
        # Traiter chaque page réelle du PDF
        for idx, page_num in enumerate(range(start_page, end_page + 1), start=1):
            logger.info(f"📄 Traitement ULTRA page PDF {page_num} ({idx}/{total_pages})")
            page_result = self.process_page_ultra(pdf_path, page_num)
            global_log['pages'].append(page_result)
            
            if page_result['success']:
                self.total_extracted += page_result['images_extracted']
                logger.info(f"  ✅ Page PDF {page_num}: {page_result['images_extracted']} images capturées")
        
        # Finaliser le log global
        global_log['end_time'] = datetime.now().isoformat()
        global_log['total_images_extracted'] = self.total_extracted
        global_log['success_pages'] = len([p for p in global_log['pages'] if p['success']])
        global_log['failed_pages'] = len([p for p in global_log['pages'] if not p['success']])
        
        # Sauvegarder le log global
        global_log_path = os.path.join(self.session_dir, "extraction_ultra_complete.json")
        with open(global_log_path, 'w', encoding='utf-8') as f:
            json.dump(global_log, f, indent=2, ensure_ascii=False)
        
        # Créer le résumé texte
        self.create_text_summary(global_log)
        
        logger.info(f"🎉 EXTRACTION ULTRA TERMINÉE: {self.total_extracted} images extraites")
        logger.info(f"📁 Résultats: {self.session_dir}")
        
        # Ouvrir le dossier automatiquement
        if os.name == 'nt':
            try:
                os.startfile(self.session_dir)
            except:
                pass
        
        return True
    
    def process_page_ultra(self, pdf_path, page_num):
        """Traite une page en mode ULTRA SENSIBLE"""
        page_start_time = time.time()
        
        # Créer le dossier de la page
        page_dir = self.create_page_folder(page_num)
        
        page_result = {
            'page_number': page_num,
            'page_dir': page_dir,
            'start_time': datetime.now().isoformat(),
            'mode': 'ULTRA_SENSIBLE',
            'success': False,
            'images_extracted': 0,
            'rectangles_found': 0,
            'images_saved': [],
            'configs_tested': [],
            'error': None
        }
        
        try:
            # Analyser les dimensions de la page
            page_analysis = self.analyze_page_dimensions(pdf_path, page_num)
            page_result['page_analysis'] = page_analysis
            
            # Convertir la page avec DPI ÉLEVÉ pour capturer plus de détails
            high_dpi = max(400, page_analysis['recommended_dpi'])  # Minimum 400 DPI
            logger.info(f"  📏 Page {page_num}: {page_analysis['page_format']} → DPI ULTRA {high_dpi}")
            
            page_images = convert_from_path(
                pdf_path, 
                dpi=high_dpi,  # DPI élevé pour plus de précision
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
            
            # NOUVEAU : Sauvegarder l'image de la page complète pour l'analyse Ollama
            page_image_path = os.path.join(page_dir, "page_full_image.jpg")
            cv2.imwrite(page_image_path, page_cv)
            logger.debug(f"  💾 Image de page sauvegardée: {page_image_path}")
            
            # NOUVEAU : Extraire tous les numéros de la page d'un coup (plus efficace)
            logger.info(f"  🔢 Extraction des numéros de la page {page_num}...")
            numbers_map = self.extract_all_page_numbers(pdf_path, page_num)
            
            # **MÉTHODE ULTRA : TESTER TOUTES LES CONFIGURATIONS POSSIBLES**
            all_rectangles = []
            
            # 1. Configurations ultra sensibles
            ultra_configs = [
                {'name': 'ultra_micro', 'sensitivity': 90, 'mode': 'general', 'min_area_div': 1000},
                {'name': 'ultra_high_contrast', 'sensitivity': 20, 'mode': 'high_contrast', 'min_area_div': 800},
                {'name': 'ultra_documents', 'sensitivity': 80, 'mode': 'documents', 'min_area_div': 600},
                {'name': 'ultra_adaptive', 'sensitivity': 60, 'mode': 'general', 'min_area_div': 400},
                {'name': 'ultra_extreme', 'sensitivity': 95, 'mode': 'general', 'min_area_div': 2000},
            ]
            
            best_rectangles = []
            best_count = 0
            
            for config in ultra_configs:
                logger.info(f"    🧪 Test config: {config['name']}")
                rectangles = self.ultra_detect_rectangles(page_cv, config)
                
                page_result['configs_tested'].append({
                    'config': config['name'],
                    'rectangles_found': len(rectangles),
                    'sensitivity': config['sensitivity']
                })
                
                logger.info(f"      → {len(rectangles)} rectangles trouvés")
                
                # Garder la config qui trouve le plus de rectangles
                if len(rectangles) > best_count:
                    best_count = len(rectangles)
                    best_rectangles = rectangles
                    page_result['best_config'] = config['name']
                
                # Ajouter tous les rectangles uniques
                for rect in rectangles:
                    if not self._is_duplicate_rectangle(rect, all_rectangles):
                        all_rectangles.append(rect)
            
            # **MÉTHODE ULTRA 2 : DÉTECTION PAR TEMPLATE MATCHING**
            template_rectangles = self.template_based_detection(page_cv)
            logger.info(f"    🎯 Template matching: {len(template_rectangles)} rectangles")
            
            for rect in template_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            # **MÉTHODE ULTRA 3 : DÉTECTION PAR ANALYSE DE COULEUR**
            color_rectangles = self.color_based_detection(page_cv)
            logger.info(f"    🌈 Color analysis: {len(color_rectangles)} rectangles")
            
            for rect in color_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            # **MÉTHODE ULTRA 4 : DÉTECTION POUR IMAGES À HAUTE BALANCE DES BLANCS**
            soft_rectangles = self.soft_edge_detection(page_cv)
            logger.info(f"    ☁️ Soft edge detection: {len(soft_rectangles)} rectangles")
            
            for rect in soft_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            # **MÉTHODE ULTRA 5 : DÉTECTION PAR SATURATION**
            sat_rectangles = self.saturation_based_detection(page_cv)
            logger.info(f"    🎨 Saturation analysis: {len(sat_rectangles)} rectangles")
            
            for rect in sat_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            # **MÉTHODE ULTRA 6 : PRÉTRAITEMENT ADAPTATIF**
            edges, image_type = self.adaptive_preprocessing(page_cv)
            if edges is not None:
                logger.info(f"    🔄 Image type detected: {image_type}")
                # Appliquer une détection spéciale sur les edges adaptés
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                adaptive_rectangles = []
                
                min_area = (page_cv.shape[0] * page_cv.shape[1]) / 1200  # Seuil adaptatif
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > min_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        
                        # Filtrer les rectangles trop déformés
                        aspect_ratio = w / h if h > 0 else 0
                        if 0.1 < aspect_ratio < 10:  # Très permissif
                            adaptive_rectangles.append({
                                'id': len(adaptive_rectangles),
                                'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                                'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                                'area': area,
                                'method': f'adaptive_{image_type}',
                                'confidence': 0.8 if image_type == 'high_white_balance' else 0.6
                            })
                
                logger.info(f"    🔄 Adaptive preprocessing: {len(adaptive_rectangles)} rectangles")
                
                for rect in adaptive_rectangles:
                    if not self._is_duplicate_rectangle(rect, all_rectangles):
                        all_rectangles.append(rect)
            
            # Utiliser TOUS les rectangles trouvés (fusion des méthodes)
            final_rectangles = all_rectangles
            page_result['rectangles_found'] = len(final_rectangles)
            page_result['rectangles_details'] = []
            
            logger.info(f"  🎯 TOTAL FINAL: {len(final_rectangles)} rectangles uniques détectés")
            
            # NOUVEAU : Créer dossier douteux
            doubtful_dir = os.path.join(page_dir, "DOUTEUX")
            os.makedirs(doubtful_dir, exist_ok=True)
            
            # Stocker toutes les images pour analyse comparative
            all_extracted_images = []
            all_rectangles_data = []
            
            # Première passe : extraire toutes les images
            for rect_idx, rectangle in enumerate(final_rectangles):
                try:
                    # Extraire l'image
                    extracted_image = self.extract_rectangle_image(page_cv, rectangle)
                    if extracted_image is None:
                        continue
                    
                    # Filtrer les images vraiment trop petites
                    if extracted_image.shape[0] < 20 or extracted_image.shape[1] < 20:
                        logger.info(f"      ⚠️ Rectangle {rect_idx+1} trop petit: {extracted_image.shape}")
                        continue
                    
                    # ROTATION DÉSACTIVÉE - Éviter les rotations incorrectes
                    # corrected_image, was_rotated = self.detect_and_fix_rotation(extracted_image, rectangle)
                    was_rotated = False
                    
                    # if was_rotated:
                    #     logger.info(f"      🔄 Image {rect_idx+1} corrigée (rotation)")
                    #     extracted_image = corrected_image
                    
                    all_extracted_images.append(extracted_image)
                    all_rectangles_data.append({
                        'image': extracted_image,
                        'rectangle': rectangle,
                        'rect_idx': rect_idx,
                        'was_rotated': was_rotated
                    })
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur rectangle {rect_idx + 1}: {e}")
                    continue
            
            # NOUVEAU : Analyser toutes les images et classifier
            for data in all_rectangles_data:
                try:
                    extracted_image = data['image']
                    rectangle = data['rectangle']
                    rect_idx = data['rect_idx']
                    was_rotated = data['was_rotated']
                    
                    # Analyser la qualité
                    quality_analysis = self.analyze_image_quality_and_validity(
                        extracted_image, 
                        [d['image'] for d in all_rectangles_data]
                    )
                    
                    # Détecter numéro d'œuvre (rotation désactivée)
                    artwork_number = self.detect_artwork_number(page_cv, rectangle, pdf_path, page_num, numbers_map)
                    
                    # Déterminer le nom et le dossier
                    if artwork_number:
                        base_filename = f"{artwork_number}.png"
                    else:
                        base_filename = f"rectangle_{rect_idx + 1:02d}.png"
                    
                    # NOUVEAU : Décider où sauvegarder
                    if quality_analysis['is_doubtful']:
                        # Sauvegarder dans le dossier DOUTEUX
                        filename = f"DOUTEUX_{base_filename}"
                        image_path = os.path.join(doubtful_dir, filename)
                        
                        # Créer un fichier info pour expliquer pourquoi c'est douteux
                        info_filename = f"{base_filename.replace('.png', '_INFO.txt')}"
                        info_path = os.path.join(doubtful_dir, info_filename)
                        with open(info_path, 'w', encoding='utf-8') as f:
                            f.write(f"IMAGE DOUTEUSE - ANALYSE AUTOMATIQUE\n")
                            f.write(f"={'=' * 40}\n\n")
                            f.write(f"Fichier: {filename}\n")
                            f.write(f"Confiance: {quality_analysis['confidence']:.2f}/1.0\n")
                            f.write(f"Dimensions: {extracted_image.shape[1]}×{extracted_image.shape[0]} pixels\n")
                            f.write(f"Taille: {(extracted_image.shape[0] * extracted_image.shape[1]) // 1000}K pixels\n")
                            f.write(f"Rotation corrigée: {'Oui' if was_rotated else 'Non'}\n\n")
                            f.write(f"RAISONS DE LA CLASSIFICATION DOUTEUSE:\n")
                            for reason in quality_analysis['reasons']:
                                reason_desc = {
                                    'taille_anormale': '• Taille anormalement petite par rapport aux autres images',
                                    'image_vide': '• Image principalement blanche/vide (>95% pixels clairs)',
                                    'ratio_extreme': '• Ratio d\'aspect extrême (trop allongée)',
                                    'peu_de_contenu': '• Peu de contenu visuel détecté (faible variance)',
                                    'pas_de_contours': '• Aucun contour significatif détecté'
                                }.get(reason, f'• {reason}')
                                f.write(f"{reason_desc}\n")
                            f.write(f"\nRECOMMANDATE:\n")
                            f.write(f"Vérifiez manuellement cette image. Elle pourrait être:\n")
                            f.write(f"- Un faux positif (bruit, fragment de page)\n")
                            f.write(f"- Une vraie image mais de mauvaise qualité\n")
                            f.write(f"- Une image nécessitant un traitement spécial\n")
                        
                        logger.info(f"    ⚠️ Sauvé (DOUTEUX): {filename} - Raisons: {', '.join(quality_analysis['reasons'])}")
                        
                        # Créer miniature dans le dossier douteux
                        thumbnail = self.create_thumbnail(extracted_image)
                        thumb_path = os.path.join(doubtful_dir, f"thumb_{filename}")
                        cv2.imwrite(thumb_path, thumbnail)
                        
                    else:
                        # Sauvegarder normalement
                        filename = base_filename
                        image_path = os.path.join(page_dir, filename)
                        logger.info(f"    ✅ Sauvé: {filename} ({extracted_image.shape[1]}×{extracted_image.shape[0]})")
                        
                        # Créer miniature normale
                        thumbnail = self.create_thumbnail(extracted_image)
                        thumb_path = os.path.join(page_dir, f"thumb_{filename}")
                        cv2.imwrite(thumb_path, thumbnail)
                    
                    # Sauvegarder l'image
                    cv2.imwrite(image_path, extracted_image)
                    
                    # Enregistrer les détails
                    rect_details = {
                        'rectangle_id': rect_idx + 1,
                        'filename': filename,
                        'is_doubtful': quality_analysis['is_doubtful'],
                        'confidence': quality_analysis['confidence'],
                        'doubt_reasons': quality_analysis['reasons'],
                        'was_rotated': was_rotated,
                        'artwork_number': artwork_number,
                        'bbox': rectangle.get('bbox'),
                        'area': rectangle.get('area'),
                        'size_kb': os.path.getsize(image_path) // 1024,
                        'thumbnail': f"thumb_{filename}",
                        'detection_method': rectangle.get('method', 'unknown'),
                        'original_confidence': rectangle.get('confidence', 0.5)
                    }
                    
                    page_result['rectangles_details'].append(rect_details)
                    page_result['images_saved'].append(filename)
                    page_result['images_extracted'] += 1
                    
                    if quality_analysis['is_doubtful']:
                        page_result['doubtful_count'] = page_result.get('doubtful_count', 0) + 1
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur sauvegarde {rect_idx + 1}: {e}")
                    continue
            
            # Afficher les numéros détectés (sans correction automatique)
            detected_numbers = []
            for rect in page_result.get('rectangles_details', []):
                artwork_number = rect.get('artwork_number')
                if artwork_number and artwork_number.isdigit():
                    detected_numbers.append(int(artwork_number))
            
            if detected_numbers:
                detected_numbers.sort()
                logger.info(f"  🔢 Numéros détectés: {detected_numbers}")
            else:
                logger.info(f"  🔢 Aucun numéro d'œuvre détecté sur cette page")
            
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
        self.create_page_text_details(page_dir, page_result)
        
        return page_result
    
    def ultra_detect_rectangles(self, image, config):
        """Détection ULTRA SENSIBLE de rectangles"""
        height, width = image.shape[:2]
        total_pixels = height * width
        
        # Prétraitement ULTRA selon le mode
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        sensitivity = config['sensitivity']
        mode = config['mode']
        min_area_div = config['min_area_div']
        
        if mode == 'documents':
            # Mode documents avec débruitage fort
            denoised = cv2.fastNlMeansDenoising(gray, h=15)
            clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(16,16))
            enhanced = clahe.apply(denoised)
            canny_low, canny_high = 2, 10  # ULTRA sensible
        elif mode == 'high_contrast':
            # Mode high contrast avec moins de débruitage
            denoised = cv2.GaussianBlur(gray, (1, 1), 0)  # Blur minimal
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4,4))
            enhanced = clahe.apply(denoised)
            canny_low = max(5, sensitivity // 10)  # Seuils très bas
            canny_high = max(15, sensitivity // 3)
        else:  # general
            # Mode général ULTRA sensible
            denoised = cv2.bilateralFilter(gray, 5, 50, 50)  # Préserve les bords
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            canny_low = max(1, sensitivity // 20)  # TRÈS sensible
            canny_high = max(5, sensitivity // 5)
        
        # Détection de bords MULTI-MÉTHODES
        # 1. Canny classique
        edges1 = cv2.Canny(enhanced, canny_low, canny_high)
        
        # 2. Canny avec seuils encore plus bas
        edges2 = cv2.Canny(enhanced, max(1, canny_low//2), max(3, canny_high//2))
        
        # 3. Gradient morphologique
        kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
        _, edges3 = cv2.threshold(gradient, sensitivity // 10, 255, cv2.THRESH_BINARY)
        
        # 4. Seuillage adaptatif
        edges4 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 7, 1)
        edges4 = cv2.bitwise_not(edges4)
        
        # Combiner TOUTES les méthodes
        combined = cv2.bitwise_or(edges1, edges2)
        combined = cv2.bitwise_or(combined, edges3)
        combined = cv2.bitwise_or(combined, edges4)
        
        # Morphologie MINIMALE pour ne pas perdre de détails
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        
        # Contours
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        rectangles = []
        min_area = total_pixels / min_area_div  # Seuil ULTRA bas
        
        for i, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
            area = cv2.contourArea(contour)
            
            # Seuil ULTRA permissif
            if area < min_area:
                continue
            
            # Vérifier que le contour n'est pas trop déformé
            bbox = cv2.boundingRect(contour)
            bbox_area = bbox[2] * bbox[3]
            area_ratio = area / bbox_area if bbox_area > 0 else 0
            
            # Rejeter les contours trop irréguliers
            if area_ratio < 0.4:  # Au moins 40% de remplissage
                continue
            
            # Approximation TRÈS permissive
            epsilon_values = [0.001, 0.002, 0.005, 0.01, 0.02, 0.03]  # Plus de tentatives
            
            for epsilon_mult in epsilon_values:
                epsilon = epsilon_mult * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    x, y, w, h = cv2.boundingRect(contour)
                    rectangles.append({
                        'id': len(rectangles),
                        'corners': approx.reshape(4, 2),
                        'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                        'area': area,
                        'method': f'ultra_{mode}',
                        'confidence': 0.7,
                        'config': config['name']
                    })
                    break
            
            # Si pas de quadrilatère, essayer rectangle englobant avec seuil TRÈS bas
            if len(rectangles) == i:  # Pas ajouté
                x, y, w, h = cv2.boundingRect(contour)
                bbox_area = w * h
                area_ratio = area / bbox_area if bbox_area > 0 else 0
                
                # Seuil ULTRA permissif pour les rectangles englobants
                if area_ratio > 0.3:  # Au lieu de 0.6
                    corners = np.array([
                        [x, y], [x + w, y], [x + w, y + h], [x, y + h]
                    ])
                    
                    rectangles.append({
                        'id': len(rectangles),
                        'corners': corners,
                        'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                        'area': area,
                        'method': f'ultra_bbox_{mode}',
                        'confidence': area_ratio,
                        'config': config['name']
                    })
            
            # Limite généreuse
            if len(rectangles) >= 50:  # Plus de rectangles autorisés
                break
        
        return rectangles
    
    def template_based_detection(self, image):
        """Détection basée sur des templates de formes communes"""
        rectangles = []
        
        try:
            # Créer des templates simples pour différentes tailles
            templates = []
            
            # Templates rectangulaires de différentes tailles
            for w, h in [(100, 150), (150, 200), (200, 250), (80, 120), (60, 80)]:
                template = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(template, (5, 5), (w-5, h-5), 255, 2)
                templates.append(('rect', template))
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            for template_name, template in templates:
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= 0.3)  # Seuil permissif
                
                for pt in zip(*locations[::-1]):
                    x, y = pt
                    w, h = template.shape[1], template.shape[0]
                    
                    rectangles.append({
                        'id': len(rectangles),
                        'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                        'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                        'area': w * h,
                        'method': f'template_{template_name}',
                        'confidence': float(result[y//template.shape[0], x//template.shape[1]]) if y//template.shape[0] < result.shape[0] and x//template.shape[1] < result.shape[1] else 0.3
                    })
        
        except Exception as e:
            logger.debug(f"Template detection error: {e}")
        
        return rectangles[:10]  # Limiter pour éviter trop de faux positifs
    
    def color_based_detection(self, image):
        """Détection basée sur l'analyse des couleurs et contrastes"""
        rectangles = []
        
        try:
            # Convertir en différents espaces colorimétriques
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 1. Détection par variance locale (zones d'intérêt)
            kernel = np.ones((15, 15), np.float32) / 225
            mean_filtered = cv2.filter2D(gray.astype(np.float32), -1, kernel)
            variance = cv2.filter2D((gray.astype(np.float32) - mean_filtered) ** 2, -1, kernel)
            
            # Seuillage sur la variance pour trouver les zones texturées
            _, variance_thresh = cv2.threshold(variance.astype(np.uint8), 30, 255, cv2.THRESH_BINARY)
            
            # 2. Détection par contraste local
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            contrast = np.sqrt(sobelx**2 + sobely**2)
            contrast_norm = ((contrast / contrast.max()) * 255).astype(np.uint8)
            _, contrast_thresh = cv2.threshold(contrast_norm, 50, 255, cv2.THRESH_BINARY)
            
            # Combiner variance et contraste
            combined = cv2.bitwise_or(variance_thresh, contrast_thresh)
            
            # Morphologie pour nettoyer
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
            combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
            
            # Trouver les contours
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            min_area = (image.shape[0] * image.shape[1]) / 1500  # Seuil très bas
            
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                
                # Rectangle englobant
                x, y, w, h = cv2.boundingRect(contour)
                
                # Vérifier que c'est pas trop déformé
                aspect_ratio = w / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5:  # Très permissif
                    rectangles.append({
                        'id': len(rectangles),
                        'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                        'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                        'area': area,
                        'method': 'color_analysis',
                        'confidence': min(1.0, area / min_area / 10)
                    })
        
        except Exception as e:
            logger.debug(f"Color detection error: {e}")
        
        return rectangles
    
    def adaptive_preprocessing(self, image):
        """Prétraitement adaptatif selon les caractéristiques de l'image"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Analyser l'histogramme
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_norm = hist.ravel() / hist.sum()
        
        # Détecter si l'image est très claire
        bright_pixels = np.sum(hist_norm[200:])  # Pixels > 200
        mid_pixels = np.sum(hist_norm[100:200])  # Pixels moyens
        dark_pixels = np.sum(hist_norm[:100])    # Pixels sombres
        
        if bright_pixels > 0.6:  # Image très claire
            # Stratégie pour images claires
            # 1. Égalisation adaptative plus douce
            clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4,4))
            enhanced = clahe.apply(gray)
            
            # 2. Détection par gradient inversé
            inverted = 255 - enhanced
            edges = cv2.Canny(inverted, 10, 30)
            
            return edges, 'high_white_balance'
        
        elif dark_pixels > 0.6:  # Image très sombre
            # Stratégie pour images sombres
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            edges = cv2.Canny(enhanced, 20, 60)
            
            return edges, 'low_brightness'
        
        else:  # Image normale
            return None, 'normal'
    
    def soft_edge_detection(self, image):
        """Détection spécialisée pour les transitions douces"""
        rectangles = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # 1. Filtre de Sobel avec seuils très bas
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Magnitude avec seuil très bas
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        
        # Normalisation douce
        magnitude_norm = np.uint8(np.clip(magnitude * 2, 0, 255))
        
        # 2. Seuillage adaptatif local
        adaptive_thresh = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_MEAN_C, 
            cv2.THRESH_BINARY,
            blockSize=31,  # Grand bloc pour capturer les transitions douces
            C=2  # Seuil très bas
        )
        
        # 3. Détection de lignes horizontales et verticales
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        horizontal_lines = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, vertical_kernel)
        
        # Combiner les lignes
        combined_lines = cv2.bitwise_or(horizontal_lines, vertical_lines)
        
        # 4. Recherche de rectangles
        contours, _ = cv2.findContours(combined_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 50 and h > 50:  # Taille minimale
                rectangles.append({
                    'id': len(rectangles),
                    'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                    'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                    'area': w * h,
                    'method': 'soft_edge',
                    'confidence': 0.6
                })
        
        return rectangles
    
    def saturation_based_detection(self, image):
        """Détection basée sur les changements de saturation"""
        rectangles = []
        
        # Convertir en HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Extraire le canal de saturation
        saturation = hsv[:, :, 1]
        
        # Les zones avec artwork ont souvent une saturation différente du fond
        # Seuillage adaptatif sur la saturation
        sat_thresh = cv2.adaptiveThreshold(
            saturation, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            21, 5
        )
        
        # Détection de contours
        contours, _ = cv2.findContours(sat_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        min_area = (image.shape[0] * image.shape[1]) / 800
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                rectangles.append({
                    'id': len(rectangles),
                    'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                    'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                    'area': area,
                    'method': 'saturation_analysis',
                    'confidence': 0.5
                })
        
        return rectangles
    
    def detect_and_fix_rotation(self, image, rectangle):
        """Détecte si l'image est mal orientée et la corrige"""
        try:
            height, width = image.shape[:2]
            
            # Détecter l'orientation principale des traits
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # NOUVEAU : Détection plus robuste avec plusieurs méthodes
            rotation_detected = False
            rotation_angle = 0
            
            # Méthode 1: Détection de lignes Hough (améliorée)
            edges = cv2.Canny(gray, 20, 80)  # Seuils encore plus bas
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=15, maxLineGap=10)
            
            if lines is not None and len(lines) > 2:
                angles = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                    angles.append(angle)
                
                # Analyser les angles dominants
                angles = np.array(angles)
                
                # Détection plus fine des orientations
                horizontal_count = np.sum(np.abs(angles) < 15)  # Plus strict
                vertical_count = np.sum(np.abs(np.abs(angles) - 90) < 15)
                diagonal_count = np.sum((np.abs(angles) > 15) & (np.abs(np.abs(angles) - 90) > 15))
                
                aspect_ratio = width / height
                
                # Décider si rotation nécessaire
                if aspect_ratio > 1.2 and vertical_count > horizontal_count * 1.2:
                    rotation_detected = True
                    rotation_angle = 90
                elif aspect_ratio < 0.8 and horizontal_count > vertical_count * 1.2:
                    rotation_detected = True
                    rotation_angle = -90
                elif diagonal_count > max(horizontal_count, vertical_count):
                    # Beaucoup de lignes diagonales = image penchée
                    # Calculer l'angle moyen des diagonales
                    diagonal_angles = angles[(np.abs(angles) > 15) & (np.abs(np.abs(angles) - 90) > 15)]
                    if len(diagonal_angles) > 3:
                        mean_angle = np.mean(diagonal_angles)
                        # Corriger si l'angle est significatif
                        if abs(mean_angle) > 10:
                            rotation_detected = True
                            rotation_angle = -mean_angle  # Correction inverse
                            logger.debug(f"      🔍 Rotation diagonale détectée: {mean_angle:.1f}°")
            
            # Méthode 2: Détection par analyse de texte (si OCR disponible)
            if not rotation_detected and hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
                try:
                    # Tester l'orientation avec Tesseract
                    osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
                    detected_angle = osd.get('rotate', 0)
                    confidence = osd.get('script_conf', 0)
                    
                    # Seuil de confiance pour accepter la rotation
                    if detected_angle != 0 and confidence > 1.0:
                        rotation_detected = True
                        rotation_angle = detected_angle
                        logger.debug(f"      🔍 Tesseract OSD: rotation {detected_angle}° (conf: {confidence})")
                except:
                    pass
            
            # Méthode 3: Détection par analyse de contours
            if not rotation_detected:
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    # Trouver le plus grand contour
                    largest_contour = max(contours, key=cv2.contourArea)
                    rect = cv2.minAreaRect(largest_contour)
                    angle = rect[2]
                    
                    # Normaliser l'angle
                    if angle < -45:
                        angle += 90
                    elif angle > 45:
                        angle -= 90
                    
                    # Si l'angle est proche de 90°, rotation nécessaire
                    if abs(angle) > 70:
                        rotation_detected = True
                        rotation_angle = 90 if angle > 0 else -90
            
            # Méthode 4: Détection de rotation 180° par analyse de texte (STRICTE)
            if not rotation_detected and hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
                try:
                    # Tester si le texte est à l'envers
                    text_original = pytesseract.image_to_string(image, config='--psm 6')
                    text_rotated = pytesseract.image_to_string(cv2.rotate(image, cv2.ROTATE_180), config='--psm 6')
                    
                    # Compter les caractères alphanumériques dans chaque version
                    import re
                    chars_original = len(re.findall(r'[a-zA-Z0-9]', text_original))
                    chars_rotated = len(re.findall(r'[a-zA-Z0-9]', text_rotated))
                    
                    # SEUIL PLUS STRICT : différence significative ET minimum de caractères
                    if chars_rotated > chars_original * 2.0 and chars_rotated > 10:
                        rotation_detected = True
                        rotation_angle = 180
                        logger.debug(f"      🔍 Rotation 180° détectée par analyse de texte (orig: {chars_original}, rot: {chars_rotated})")
                except:
                    pass
            
            if rotation_detected:
                logger.info(f"      🔄 Rotation détectée: {rotation_angle}°")
                
                if rotation_angle == 180:
                    # Rotation simple de 180°
                    rotated = cv2.rotate(image, cv2.ROTATE_180)
                    return rotated, True
                else:
                    # Rotation de 90° ou -90°
                    center = (width // 2, height // 2)
                    M = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
                    
                    # Calculer nouvelles dimensions après rotation
                    if abs(rotation_angle) == 90:
                        new_width = height
                        new_height = width
                    else:
                        new_width = width
                        new_height = height
                    
                    # Ajuster la matrice de transformation pour éviter le découpage
                    M[0, 2] += (new_width - width) / 2
                    M[1, 2] += (new_height - height) / 2
                    
                    rotated = cv2.warpAffine(image, M, (new_width, new_height))
                    return rotated, True
            
            return image, False
            
        except Exception as e:
            logger.debug(f"Erreur détection rotation: {e}")
            return image, False
    
    def analyze_image_quality_and_validity(self, image, all_images_in_page):
        """Analyse si une image est douteuse"""
        reasons = []
        confidence = 1.0
        
        height, width = image.shape[:2]
        
        # 1. Vérifier les dimensions suspectes
        if all_images_in_page:
            # Calculer les statistiques de taille de la page
            sizes = [(img.shape[0] * img.shape[1]) for img in all_images_in_page]
            mean_size = np.mean(sizes)
            std_size = np.std(sizes)
            current_size = height * width
            
            # Si beaucoup plus petit que la moyenne
            if current_size < mean_size - 2 * std_size:
                reasons.append("taille_anormale")
                confidence *= 0.5
        
        # 2. Vérifier si c'est principalement blanc/vide
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        white_pixels = np.sum(gray > 240) / gray.size
        
        if white_pixels > 0.95:
            reasons.append("image_vide")
            confidence *= 0.2
        
        # 3. Vérifier le ratio d'aspect
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 8:  # Très allongé
            reasons.append("ratio_extreme")
            confidence *= 0.6
        
        # 4. Vérifier la variance (image uniforme)
        variance = np.var(gray)
        if variance < 100:
            reasons.append("peu_de_contenu")
            confidence *= 0.4
        
        # 5. Détection de contours
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        
        if edge_ratio < 0.01:
            reasons.append("pas_de_contours")
            confidence *= 0.3
        
        is_doubtful = confidence < 0.7 or len(reasons) > 1
        
        return {
            'is_doubtful': is_doubtful,
            'confidence': confidence,
            'reasons': reasons
        }
    
    def _is_duplicate_rectangle(self, new_rect, existing_rects):
        """Vérifie si un rectangle est un doublon (version améliorée)"""
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
            if center_distance < max_dim * 0.15:  # 15% de la plus grande dimension (plus strict)
                # Vérifier aussi la similarité des tailles
                size_ratio_w = min(new_w, ex_w) / max(new_w, ex_w)
                size_ratio_h = min(new_h, ex_h) / max(new_h, ex_h)
                
                if size_ratio_w > 0.8 and size_ratio_h > 0.8:  # Plus strict
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
    
    def analyze_page_dimensions(self, pdf_path, page_number):
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
                'recommended_dpi': 400  # DPI plus élevé par défaut
            }
    
    def _identify_page_format(self, width_mm, height_mm):
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
    
    def _calculate_optimal_dpi(self, width_mm, height_mm, area_mm2):
        """Calcule le DPI optimal - PLUS ÉLEVÉ pour mode ULTRA"""
        if area_mm2 < 30000:  # < A5
            return 500  # Augmenté
        elif area_mm2 < 70000:  # A5-A4
            return 400  # Augmenté
        elif area_mm2 < 150000:  # A4-A3
            return 350  # Augmenté
        else:  # > A3
            return 300  # Augmenté
    
    def extract_rectangle_image(self, image, rectangle):
        """Extrait l'image avec détection intelligente de rotation et privilégie extraction simple"""
        try:
            bbox = rectangle['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # EXTRACTION SIMPLE UNIQUEMENT - Éviter les déformations
            bbox_image = image[y:y+h, x:x+w].copy()
            logger.debug(f"      ✅ Extraction directe (bbox: {w}×{h})")
            return bbox_image
            
        except Exception as e:
            logger.error(f"Erreur extraction rectangle: {e}")
            # Fallback sur bbox simple
            try:
                bbox = rectangle['bbox']
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                return image[y:y+h, x:x+w]
            except:
                return None
    
    def _order_points(self, pts):
        """Ordonne les points pour la transformation"""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect
    
    def _adjust_rectangle_for_rotation(self, rectangle, was_rotated):
        """Ajuste les coordonnées du rectangle si l'image a été tournée"""
        if not was_rotated:
            return rectangle
        
        # Pour l'instant, on retourne le rectangle tel quel
        # L'OCR se fera sur la page originale, donc les coordonnées restent les mêmes
        # La rotation n'affecte que l'image extraite, pas sa position sur la page
        return rectangle
    
    def detect_artwork_number(self, image, rectangle, pdf_path=None, page_num=None, numbers_map=None):
        """Détecte le numéro d'œuvre sous l'image (méthode optimisée).
        - Utilise d'abord l'OCR existant du PDF si disponible
        - Sinon, cherche UNIQUEMENT sous le rectangle (zone prioritaire)
        - OCR simple avec un seul prétraitement
        - Retourne une chaîne du numéro ou None.
        """
        try:
            # 1. ESSAYER D'ABORD L'OCR EXISTANT DU PDF (méthode optimisée)
            if pdf_path and page_num and numbers_map is not None:
                # Utiliser la map des numéros déjà extraite
                nearest_number = self.find_nearest_number(rectangle, numbers_map)
                if nearest_number:
                    return nearest_number
            
            # 2. FALLBACK : OCR sur l'image
            # Vérifier Tesseract
            if not hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
                return None
            
            H, W = image.shape[:2]
            bbox = rectangle.get('bbox', {})
            x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)

            # ZONES DE RECHERCHE ÉLARGIES : Sous, droite, gauche
            pad_x = max(20, w // 10)
            pad_y = max(20, h // 10)
            
            search_zones = [
                # Zone 1: Sous l'image (priorité maximale)
                {
                    'name': 'sous',
                    'x': max(0, x - pad_x),
                    'y': min(H - 1, y + h + 2),
                    'w': min(W - max(0, x - pad_x), w + 2 * pad_x),
                    'h': min(80, H - min(H - 1, y + h + 2)),
                    'weight': 3.0
                },
                # Zone 2: À droite de l'image
                {
                    'name': 'droite',
                    'x': min(W - 1, x + w + 2),
                    'y': max(0, y - pad_y),
                    'w': min(100, W - min(W - 1, x + w + 2)),
                    'h': min(h + 2 * pad_y, H - max(0, y - pad_y)),
                    'weight': 2.0
                },
                # Zone 3: À gauche de l'image
                {
                    'name': 'gauche',
                    'x': max(0, x - 100),
                    'y': max(0, y - pad_y),
                    'w': min(100, x),
                    'h': min(h + 2 * pad_y, H - max(0, y - pad_y)),
                    'weight': 1.5
                }
            ]
            
            best_number = None
            best_score = 0
            
            for zone in search_zones:
                if zone['w'] <= 5 or zone['h'] <= 5:
                    continue
                
                # Extraire la zone
                roi = image[zone['y']:zone['y']+zone['h'], zone['x']:zone['x']+zone['w']]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                
                # PRÉTRAITEMENT SIMPLE : OTSU uniquement
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Agrandir pour améliorer OCR
                binary = cv2.resize(binary, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                
                # OCR SIMPLE : Une seule configuration
                try:
                    text = pytesseract.image_to_string(binary, config='--psm 8 -c tessedit_char_whitelist=0123456789')
                except Exception:
                    continue
                
                # EXTRACTION SIMPLE : Nombres 1-3 chiffres uniquement
                numbers = re.findall(r'\b([0-9]{1,3})\b', text.strip())
                
                if numbers:
                    # Prendre le premier nombre trouvé
                    number = numbers[0]
                    score = zone['weight']
                    
                    logger.debug(f"      🔍 Zone {zone['name']}: '{text.strip()}' → num '{number}' (score: {score})")
                    
                    if score > best_score:
                        best_score = score
                        best_number = number
                        logger.info(f"      🎯 Nouveau meilleur: {number} (zone {zone['name']}, score: {score})")
            
            if best_number:
                logger.info(f"      ✅ Numéro final détecté: {best_number}")
                return best_number
            else:
                logger.debug(f"      ❌ Aucun numéro détecté dans toutes les zones")
                return None
                
        except Exception as e:
            logger.debug(f"      ❌ Erreur détection numéro: {e}")
            return None
    
    def extract_all_page_numbers(self, pdf_path, page_num):
        """Extrait tous les numéros de la page avec leurs positions"""
        try:
            logger.debug(f"      📄 Extraction de tous les numéros de la page {page_num}")
            
            numbers_map = {}
            
            with pdfplumber.open(pdf_path) as pdf:
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    words = page.extract_words()
                    
                    for word in words:
                        if word['text'].isdigit() and 1 <= len(word['text']) <= 3:
                            # Stocker avec position
                            numbers_map[(word['x0'], word['top'])] = word['text']
                            logger.debug(f"      🔢 Numéro détecté: {word['text']} à ({word['x0']:.1f}, {word['top']:.1f})")
            
            logger.info(f"      📊 Total numéros trouvés sur la page: {len(numbers_map)}")
            return numbers_map
            
        except Exception as e:
            logger.error(f"      ❌ Erreur extraction numéros: {e}")
            return {}
    
    def find_nearest_number(self, rectangle, numbers_map):
        """Trouve le numéro le plus proche du rectangle"""
        bbox = rectangle['bbox']
        rect_center_x = bbox['x'] + bbox['w']/2
        rect_bottom_y = bbox['y'] + bbox['h']
        
        best_number = None
        best_distance = float('inf')
        
        for (num_x, num_y), number in numbers_map.items():
            # Distance pondérée (privilégier sous l'image)
            # Le numéro doit être sous l'image (num_y > rect_bottom_y)
            if num_y > rect_bottom_y:
                distance = abs(rect_center_x - num_x) + 2 * (num_y - rect_bottom_y)
                
                if distance < best_distance:
                    best_distance = distance
                    best_number = number
                    logger.debug(f"      🎯 Meilleur candidat: {number} à ({num_x:.1f}, {num_y:.1f}) - distance: {distance:.1f}")
        
        if best_number:
            logger.info(f"      ✅ Numéro associé: {best_number} (distance: {best_distance:.1f})")
        else:
            logger.debug(f"      ❌ Aucun numéro trouvé sous ce rectangle")
        
        return best_number

    def _try_use_existing_ocr(self, pdf_path, page_num, rectangle):
        """Utilise l'OCR déjà présent dans le PDF avec pdfplumber"""
        try:
            logger.debug(f"      📄 Extraction OCR existant du PDF: {os.path.basename(pdf_path)}")
            
            with pdfplumber.open(pdf_path) as pdf:
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    
                    # Récupérer le texte avec les coordonnées
                    words = page.extract_words()
                    
                    # Chercher les numéros près du rectangle
                    bbox = rectangle.get('bbox', {})
                    x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)
                    
                    # Coordonnées du centre et bas du rectangle
                    rect_center_x = x + w / 2
                    rect_bottom_y = y + h
                    
                    best_number = None
                    best_distance = float('inf')
                    
                    for word in words:
                        # Si c'est un nombre de 1-3 chiffres
                        if word['text'].isdigit() and 1 <= len(word['text']) <= 3:
                            word_x = word['x0']
                            word_y = word['top']
                            
                            # Distance pondérée (privilégier sous l'image)
                            # Le numéro doit être sous l'image (word_y > rect_bottom_y)
                            if word_y > rect_bottom_y:
                                # Distance horizontale + 2x distance verticale (privilégier la proximité verticale)
                                distance = abs(word_x - rect_center_x) + 2 * (word_y - rect_bottom_y)
                                
                                if distance < best_distance:
                                    best_distance = distance
                                    best_number = word['text']
                                    logger.debug(f"      🔍 Numéro candidat: {word['text']} à ({word_x:.1f}, {word_y:.1f}) - distance: {distance:.1f}")
                    
                    if best_number:
                        logger.info(f"      📄 Numéro trouvé via OCR existant: {best_number} (distance: {best_distance:.1f})")
                        return best_number
                    else:
                        logger.debug(f"      ❌ Aucun numéro trouvé sous le rectangle dans l'OCR existant")
                        
            return None
        except Exception as e:
            logger.debug(f"      ❌ Erreur extraction OCR existant: {e}")
            return None
    
    # Méthode supprimée - plus de correction automatique des numéros
    
    # Méthode supprimée - plus de correction automatique
    
    # Méthode supprimée - plus de correction automatique
    
    # Méthode supprimée - plus de correction automatique
    
    # Méthode supprimée - plus de correction automatique
    
    # Méthode supprimée - plus de correction automatique
    
    def _get_page_image_for_analysis(self, page_result):
        """Récupère l'image de la page pour l'analyse Ollama"""
        try:
            # Sauvegarder l'image de la page dans le dossier de la page
            page_dir = page_result.get('page_dir', '')
            page_image_path = os.path.join(page_dir, "page_full_image.jpg")
            
            # Si l'image de la page n'existe pas encore, la créer
            if not os.path.exists(page_image_path):
                # Cette méthode devrait être appelée depuis process_page_ultra
                # avec l'image de la page en paramètre
                return None
            
            # Charger l'image de la page
            page_image = cv2.imread(page_image_path)
            return page_image
        except:
            return None
    
    # Toutes les méthodes de correction automatique supprimées
    
    def create_thumbnail(self, image, max_size=200):
        """Crée une miniature"""
        height, width = image.shape[:2]
        
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    def create_page_text_details(self, page_dir, page_result):
        """Crée un fichier texte avec les détails de la page"""
        details_path = os.path.join(page_dir, "README_ULTRA.txt")
        
        content = f"""PAGE {page_result['page_number']} - EXTRACTION ULTRA SENSIBLE
{'=' * 60}

MODE: ULTRA SENSIBLE - Capture TOUT !
- Statut: {'✅ Succès' if page_result['success'] else '❌ Échec'}
- Temps de traitement: {page_result['processing_time']}s
- Images extraites: {page_result['images_extracted']}
- Rectangles détectés: {page_result['rectangles_found']}
- DPI utilisé: {page_result.get('dpi_used', 'N/A')} (ULTRA HAUTE RÉSOLUTION)

CONFIGURATIONS TESTÉES:
"""
        
        for config in page_result.get('configs_tested', []):
            content += f"- {config['config']}: {config['rectangles_found']} rectangles (sens: {config['sensitivity']})\n"
        
        content += f"""
MEILLEURE CONFIG: {page_result.get('best_config', 'N/A')}

ANALYSE DE PAGE:
- Format: {page_result.get('page_analysis', {}).get('page_format', 'N/A')}
- Taille physique: {page_result.get('page_analysis', {}).get('width_mm', 0):.1f}×{page_result.get('page_analysis', {}).get('height_mm', 0):.1f}mm
- Taille image: {page_result.get('image_size', 'N/A')}
- Mégapixels: {page_result.get('image_megapixels', 0)}MP

NUMÉROS D'ŒUVRES DÉTECTÉS:
"""
        
        # Afficher les numéros détectés (sans correction)
        detected_numbers = []
        for rect in page_result.get('rectangles_details', []):
            artwork_number = rect.get('artwork_number')
            if artwork_number and artwork_number.isdigit():
                detected_numbers.append(int(artwork_number))
        
        if detected_numbers:
            detected_numbers.sort()
            content += f"- Numéros détectés: {detected_numbers}\n"
            content += f"- Total: {len(detected_numbers)} numéros d'œuvres\n"
        else:
            content += "- Aucun numéro d'œuvre détecté sur cette page\n"

        content += f"""
IMAGES EXTRAITES:
"""
        
        if page_result['images_saved']:
            for i, img_name in enumerate(page_result['images_saved'], 1):
                # Trouver les détails correspondants
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
MÉTHODES UTILISÉES:
✅ Détection multi-configurations (5 configs testées)
✅ Template matching (formes communes)
✅ Analyse de couleur et contraste
✅ Détection de contours doux (transitions subtiles)
✅ Analyse de saturation (balance des blancs)
✅ Prétraitement adaptatif selon l'histogramme
✅ Détection et correction automatique de rotation
✅ Classification automatique des images douteuses
✅ Extraction intelligente (privilégie bbox simple)
✅ Seuils ultra-permissifs
✅ DPI élevé pour plus de précision
✅ Fusion intelligente des résultats
✅ Déduplication avancée par centre et taille
✅ Détection des numéros d'œuvres (sans correction automatique)

FICHIERS DANS CE DOSSIER:
- README_ULTRA.txt (ce fichier)
- page_ultra_details.json (données techniques complètes)
- *.png (images extraites de bonne qualité)
- thumb_*.png (miniatures 200px)
- DOUTEUX/ (dossier des images suspectes)
  ├── DOUTEUX_*.png (images classées douteuses)
  ├── *_INFO.txt (explications détaillées)
  └── thumb_*.png (miniatures des images douteuses)

Extraction ULTRA effectuée le {page_result.get('start_time', 'N/A')}
"""
        
        with open(details_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def create_text_summary(self, global_log):
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
- Durée totale: {self._calculate_duration(global_log['start_time'], global_log['end_time'])}

RÉSULTATS ULTRA:
- Pages traitées: {global_log['total_pages']}
- Pages réussies: {global_log['success_pages']}
- Pages échouées: {global_log['failed_pages']}
- Images extraites: {global_log['total_images_extracted']} ⚡ ULTRA SENSIBLE

DÉTAIL PAR PAGE:
"""
        
        for page in global_log['pages']:
            status = "✅" if page['success'] else "❌"
            doubtful_count = page.get('doubtful_count', 0)
            good_count = page['images_extracted'] - doubtful_count
            doubtful_info = f" ({doubtful_count} douteuses)" if doubtful_count > 0 else ""
            content += f"  Page {page['page_number']:3d}: {status} {good_count:2d} images{doubtful_info} "
            content += f"({page['processing_time']:4.1f}s) - {page.get('best_config', 'N/A')}\n"
        
        content += f"""
TECHNOLOGIES ULTRA UTILISÉES:
🔬 Multi-détection (8+ algorithmes par page)
🎯 Template matching intelligent
🌈 Analyse de couleur et contraste
☁️ Détection de contours doux (transitions subtiles)
🎨 Analyse de saturation (balance des blancs)
🔄 Prétraitement adaptatif selon l'histogramme
🔄 Détection et correction automatique de rotation
🤖 Classification automatique des images douteuses
🎯 Extraction intelligente (privilégie bbox simple)
📐 Seuils ultra-permissifs
🔍 DPI élevé (400+ par page)
🧠 Fusion intelligente des résultats
🚫 Déduplication avancée par centre et taille
🔍 Détection des numéros d'œuvres (sans correction automatique)

ORGANISATION DES FICHIERS:
- Dossier principal: {os.path.basename(self.session_dir)}
- Structure: page_XXX/
  ├── README_ULTRA.txt (détails de la page)
  ├── page_ultra_details.json (données techniques)
  ├── *.png (images de bonne qualité)
  ├── thumb_*.png (miniatures)
  └── DOUTEUX/
      ├── DOUTEUX_*.png (images suspectes)
      ├── *_INFO.txt (explications)
  └── thumb_*.png (miniatures)

FICHIERS GLOBAUX:
- RÉSUMÉ_ULTRA.txt (ce fichier)
- extraction_ultra_complete.json (log technique complet)

🎉 RÉSULTAT: {global_log['total_images_extracted']} images extraites avec le mode ULTRA !
   Aucune image ne devrait être ratée avec cette méthode.
"""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _calculate_duration(self, start_time, end_time):
        """Calcule la durée entre deux timestamps ISO"""
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration = end - start
            
            total_seconds = int(duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        except:
            return "N/A"


def main():
    """Fonction principale"""
    print("🚀 EXTRACTEUR PDF ULTRA SENSIBLE")
    print("=" * 60)
    print("🎯 MODE ULTRA : CAPTURE VRAIMENT TOUT !")
    print("✨ Multi-détection, seuils ultra-bas, DPI élevé")
    print("🔬 8+ algorithmes par page, fusion intelligente")
    print("☁️ Spécialisé pour fonds clairs et balance des blancs")
    print("🎨 Détection par saturation et contours doux")
    print("🔍 Détection des numéros d'œuvres (sans correction automatique)")
    print("=" * 60)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Demander la page de départ (optionnel)
    start_page_input = input("🔢 Page de départ (1 par défaut): ").strip()
    start_page = 1
    if start_page_input and start_page_input.isdigit():
        start_page = int(start_page_input)
    
    # Demander le nombre de pages (optionnel)
    max_pages_input = input("📄 Nombre max de pages (Entrée = jusqu'à la fin): ").strip()
    max_pages = None
    if max_pages_input and max_pages_input.isdigit():
        max_pages = int(max_pages_input)
    
    # Créer l'extracteur ULTRA
    extractor = UltraSensitivePDFExtractor()
    
    # Lancer l'extraction ULTRA
    print("\n🚀 Extraction ULTRA en cours...")
    print("⚡ Chaque page testée avec 8+ méthodes différentes")
    print("🔬 Seuils ultra-permissifs, DPI élevé")
    print("☁️ Optimisé pour fonds clairs et balance des blancs")
    print("🔍 Détection des numéros d'œuvres (sans correction automatique)")
    
    success = extractor.extract_pdf(pdf_path, max_pages, start_page)
    
    if success:
        print("\n✅ Extraction ULTRA terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Mode ULTRA: Toutes les images devraient être capturées !")
    else:
        print("\n❌ Extraction ULTRA échouée!")


if __name__ == "__main__":
    main()
