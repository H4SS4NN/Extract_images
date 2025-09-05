#!/usr/bin/env python3
"""
Script d'extraction PDF SMART QUALITY - Gestion intelligente de la qualité
Vérifie la qualité des extractions et OCR par tâtonnement
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

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartQualityPDFExtractor:
    def __init__(self):
        self.output_base_dir = "extractions_smart"
        self.session_dir = None
        self.total_extracted = 0
        self.quality_threshold = 0.5  # 50% minimum de qualité
        
        # Configuration Tesseract
        self._configure_tesseract()
    
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
    
    def create_session_folder(self, pdf_name):
        """Crée le dossier de session principal"""
        clean_name = os.path.splitext(pdf_name)[0]
        clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = f"{clean_name}_SMART_{timestamp}"
        
        self.session_dir = os.path.join(self.output_base_dir, session_name)
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Créer dossiers de qualité
        os.makedirs(os.path.join(self.session_dir, "qualite_OK"), exist_ok=True)
        os.makedirs(os.path.join(self.session_dir, "qualite_DOUTEUSE"), exist_ok=True)
        
        logger.info(f"📁 Session SMART créée: {self.session_dir}")
        return self.session_dir
    
    def create_page_folder(self, page_num):
        """Crée un dossier pour une page spécifique"""
        page_dir = os.path.join(self.session_dir, f"page_{page_num:03d}")
        os.makedirs(page_dir, exist_ok=True)
        return page_dir
    
    def extract_pdf(self, pdf_path, max_pages=None):
        """Extraction complète SMART QUALITY d'un PDF"""
        if not os.path.exists(pdf_path):
            logger.error(f"❌ Fichier non trouvé: {pdf_path}")
            return False
        
        logger.info(f"🚀 EXTRACTION SMART QUALITY: {os.path.basename(pdf_path)}")
        logger.info("🎯 MODE SMART: Vérification qualité + OCR par tâtonnement")
        
        # Créer la session
        pdf_name = os.path.basename(pdf_path)
        self.create_session_folder(pdf_name)
        
        # Compter les pages
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"❌ Impossible de lire le PDF: {e}")
            return False
        
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        logger.info(f"📄 {total_pages} pages à traiter en mode SMART")
        
        # Créer le fichier de résumé global
        global_log = {
            'pdf_name': pdf_name,
            'pdf_path': pdf_path,
            'session_dir': self.session_dir,
            'mode': 'SMART_QUALITY',
            'quality_threshold': self.quality_threshold,
            'start_time': datetime.now().isoformat(),
            'total_pages': total_pages,
            'pages': []
        }
        
        # Traiter chaque page
        for page_num in range(1, total_pages + 1):
            logger.info(f"📄 Traitement SMART page {page_num}/{total_pages}")
            
            page_result = self.process_page_smart(pdf_path, page_num)
            global_log['pages'].append(page_result)
            
            if page_result['success']:
                self.total_extracted += page_result['images_extracted']
                logger.info(f"  ✅ Page {page_num}: {page_result['images_extracted']} images (OK: {page_result['quality_ok']}, Douteuse: {page_result['quality_doubtful']})")
        
        # Finaliser le log global
        global_log['end_time'] = datetime.now().isoformat()
        global_log['total_images_extracted'] = self.total_extracted
        global_log['success_pages'] = len([p for p in global_log['pages'] if p['success']])
        global_log['failed_pages'] = len([p for p in global_log['pages'] if not p['success']])
        
        # Statistiques de qualité
        total_ok = sum(p.get('quality_ok', 0) for p in global_log['pages'])
        total_doubtful = sum(p.get('quality_doubtful', 0) for p in global_log['pages'])
        global_log['quality_stats'] = {
            'total_ok': total_ok,
            'total_doubtful': total_doubtful,
            'quality_ratio': total_ok / (total_ok + total_doubtful) if (total_ok + total_doubtful) > 0 else 0
        }
        
        # Sauvegarder le log global
        global_log_path = os.path.join(self.session_dir, "extraction_smart_complete.json")
        with open(global_log_path, 'w', encoding='utf-8') as f:
            json.dump(global_log, f, indent=2, ensure_ascii=False)
        
        # Créer le résumé texte
        self.create_text_summary(global_log)
        
        logger.info(f"🎉 EXTRACTION SMART TERMINÉE: {self.total_extracted} images extraites")
        logger.info(f"   📊 Qualité OK: {total_ok}, Douteuse: {total_doubtful}")
        logger.info(f"📁 Résultats: {self.session_dir}")
        
        # Ouvrir le dossier automatiquement
        if os.name == 'nt':
            try:
                os.startfile(self.session_dir)
            except:
                pass
        
        return True
    
    def process_page_smart(self, pdf_path, page_num):
        """Traite une page en mode SMART QUALITY"""
        page_start_time = time.time()
        
        # Créer le dossier de la page
        page_dir = self.create_page_folder(page_num)
        
        page_result = {
            'page_number': page_num,
            'page_dir': page_dir,
            'start_time': datetime.now().isoformat(),
            'mode': 'SMART_QUALITY',
            'success': False,
            'images_extracted': 0,
            'quality_ok': 0,
            'quality_doubtful': 0,
            'rectangles_found': 0,
            'images_saved': [],
            'configs_tested': [],
            'error': None
        }
        
        try:
            # Analyser les dimensions de la page
            page_analysis = self.analyze_page_dimensions(pdf_path, page_num)
            page_result['page_analysis'] = page_analysis
            
            # Convertir la page avec DPI ÉLEVÉ
            high_dpi = max(400, page_analysis['recommended_dpi'])
            logger.info(f"  📏 Page {page_num}: {page_analysis['page_format']} → DPI {high_dpi}")
            
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
            
            # **DÉTECTION ULTRA SENSIBLE**
            all_rectangles = []
            
            # Configurations ultra sensibles
            ultra_configs = [
                {'name': 'ultra_micro', 'sensitivity': 90, 'mode': 'general', 'min_area_div': 1000},
                {'name': 'ultra_high_contrast', 'sensitivity': 20, 'mode': 'high_contrast', 'min_area_div': 800},
                {'name': 'ultra_documents', 'sensitivity': 80, 'mode': 'documents', 'min_area_div': 600},
                {'name': 'ultra_adaptive', 'sensitivity': 60, 'mode': 'general', 'min_area_div': 400},
                {'name': 'ultra_extreme', 'sensitivity': 95, 'mode': 'general', 'min_area_div': 2000},
            ]
            
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
                
                if len(rectangles) > best_count:
                    best_count = len(rectangles)
                    page_result['best_config'] = config['name']
                
                # Ajouter tous les rectangles uniques
                for rect in rectangles:
                    if not self._is_duplicate_rectangle(rect, all_rectangles):
                        all_rectangles.append(rect)
            
            # **MÉTHODES SUPPLÉMENTAIRES**
            template_rectangles = self.template_based_detection(page_cv)
            logger.info(f"    🎯 Template matching: {len(template_rectangles)} rectangles")
            
            for rect in template_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            color_rectangles = self.color_based_detection(page_cv)
            logger.info(f"    🌈 Color analysis: {len(color_rectangles)} rectangles")
            
            for rect in color_rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
            
            # Utiliser TOUS les rectangles trouvés
            final_rectangles = all_rectangles
            page_result['rectangles_found'] = len(final_rectangles)
            page_result['rectangles_details'] = []
            
            logger.info(f"  🎯 TOTAL FINAL: {len(final_rectangles)} rectangles détectés")
            
            # **EXTRACTION AVEC VÉRIFICATION DE QUALITÉ**
            for rect_idx, rectangle in enumerate(final_rectangles):
                try:
                    # Extraire l'image
                    extracted_image = self.extract_rectangle_image(page_cv, rectangle)
                    if extracted_image is None:
                        continue
                    
                    # **VÉRIFICATION DE QUALITÉ INTELLIGENTE**
                    quality_score = self.assess_image_quality(extracted_image, rectangle)
                    
                    # Filtrer les images trop petites
                    if extracted_image.shape[0] < 30 or extracted_image.shape[1] < 30:
                        logger.info(f"      ⚠️ Rectangle {rect_idx+1} trop petit: {extracted_image.shape}")
                        continue
                    
                    # **OCR PAR TÂTONNEMENT INTELLIGENT**
                    artwork_number = self.smart_ocr_detection(page_cv, rectangle)
                    
                    # Déterminer le nom de fichier
                    if artwork_number:
                        filename = f"oeuvre_{artwork_number}.png"
                    else:
                        filename = f"rectangle_{rect_idx + 1:02d}.png"
                    
                    # **CLASSIFICATION PAR QUALITÉ**
                    if quality_score >= self.quality_threshold:
                        # Qualité OK - dossier principal + copie dans qualite_OK
                        image_path = os.path.join(page_dir, filename)
                        quality_path = os.path.join(self.session_dir, "qualite_OK", f"p{page_num:03d}_{filename}")
                        quality_status = "OK"
                        page_result['quality_ok'] += 1
                    else:
                        # Qualité douteuse - dossier principal + copie dans qualite_DOUTEUSE
                        image_path = os.path.join(page_dir, f"DOUTEUX_{filename}")
                        quality_path = os.path.join(self.session_dir, "qualite_DOUTEUSE", f"p{page_num:03d}_{filename}")
                        quality_status = "DOUTEUX"
                        page_result['quality_doubtful'] += 1
                    
                    # Sauvegarder dans le dossier de page
                    cv2.imwrite(image_path, extracted_image)
                    
                    # Sauvegarder dans le dossier de qualité
                    cv2.imwrite(quality_path, extracted_image)
                    
                    # Créer une miniature
                    thumbnail = self.create_thumbnail(extracted_image)
                    thumb_path = os.path.join(page_dir, f"thumb_{os.path.basename(image_path)}")
                    cv2.imwrite(thumb_path, thumbnail)
                    
                    # Enregistrer les détails
                    rect_details = {
                        'rectangle_id': rect_idx + 1,
                        'filename': os.path.basename(image_path),
                        'artwork_number': artwork_number,
                        'quality_score': round(quality_score, 3),
                        'quality_status': quality_status,
                        'bbox': rectangle.get('bbox'),
                        'area': rectangle.get('area'),
                        'size_kb': os.path.getsize(image_path) // 1024,
                        'thumbnail': f"thumb_{os.path.basename(image_path)}",
                        'detection_method': rectangle.get('method', 'unknown'),
                        'confidence': rectangle.get('confidence', 0.5),
                        'ocr_attempts': rectangle.get('ocr_attempts', 0)
                    }
                    
                    page_result['rectangles_details'].append(rect_details)
                    page_result['images_saved'].append(os.path.basename(image_path))
                    page_result['images_extracted'] += 1
                    
                    logger.info(f"    ✅ Sauvé: {os.path.basename(image_path)} (qualité: {quality_score:.2f} - {quality_status})")
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur rectangle {rect_idx + 1}: {e}")
                    continue
            
            page_result['success'] = True
            
        except Exception as e:
            logger.error(f"  ❌ Erreur page {page_num}: {e}")
            page_result['error'] = str(e)
        
        # Calculer le temps de traitement
        page_result['processing_time'] = round(time.time() - page_start_time, 2)
        page_result['end_time'] = datetime.now().isoformat()
        
        # Sauvegarder le log de la page
        page_log_path = os.path.join(page_dir, "page_smart_details.json")
        with open(page_log_path, 'w', encoding='utf-8') as f:
            json.dump(page_result, f, indent=2, ensure_ascii=False)
        
        # Créer le fichier texte de détails
        self.create_page_text_details(page_dir, page_result)
        
        return page_result
    
    def assess_image_quality(self, image, rectangle):
        """Évalue la qualité d'une image extraite (0.0 à 1.0)"""
        try:
            height, width = image.shape[:2]
            
            # 1. Score de taille (plus c'est grand, mieux c'est)
            size_score = min(1.0, (width * height) / 50000)  # Normalisé sur 50k pixels
            
            # 2. Score de netteté (variance du Laplacien)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 1000)  # Normalisé
            
            # 3. Score de contraste (écart-type)
            contrast_score = min(1.0, np.std(gray) / 80)  # Normalisé sur 80
            
            # 4. Score de forme (ratio d'aspect raisonnable)
            aspect_ratio = max(width, height) / min(width, height)
            shape_score = max(0.0, 1.0 - (aspect_ratio - 1) / 4)  # Pénalise les ratios > 5:1
            
            # 5. Score de remplissage (éviter les images trop vides)
            bbox = rectangle.get('bbox', {})
            if 'area' in rectangle and bbox:
                bbox_area = bbox.get('w', 1) * bbox.get('h', 1)
                fill_score = rectangle['area'] / bbox_area if bbox_area > 0 else 0.5
            else:
                fill_score = 0.5
            
            # Score final pondéré
            final_score = (
                size_score * 0.2 +      # 20% - taille
                sharpness_score * 0.3 + # 30% - netteté
                contrast_score * 0.25 + # 25% - contraste
                shape_score * 0.15 +    # 15% - forme
                fill_score * 0.1        # 10% - remplissage
            )
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.debug(f"Erreur évaluation qualité: {e}")
            return 0.5  # Score neutre en cas d'erreur
    
    def smart_ocr_detection(self, image, rectangle):
        """OCR par tâtonnement intelligent avec différentes distances"""
        try:
            # Vérifier si Tesseract est disponible
            if not hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
                return None
            
            bbox = rectangle['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # **TÂTONNEMENT INTELLIGENT**
            # Distances à tester (en pixels sous le rectangle)
            test_distances = [5, 10, 15, 20, 30, 50]
            test_heights = [40, 60, 80, 100]  # Hauteurs de zone à tester
            
            ocr_attempts = 0
            
            for distance in test_distances:
                for zone_height in test_heights:
                    ocr_attempts += 1
                    
                    # Zone de recherche
                    search_y = y + h + distance
                    search_x = max(0, x - 20)  # Un peu à gauche aussi
                    search_w = min(w + 40, image.shape[1] - search_x)  # Un peu plus large
                    search_h = zone_height
                    
                    # Vérifier les limites
                    if (search_x >= 0 and search_y >= 0 and 
                        search_x + search_w < image.shape[1] and 
                        search_y + search_h < image.shape[0]):
                        
                        search_zone = image[search_y:search_y+search_h, search_x:search_x+search_w]
                        
                        # **PRÉTRAITEMENT OCR OPTIMISÉ**
                        gray = cv2.cvtColor(search_zone, cv2.COLOR_BGR2GRAY)
                        
                        # Améliorer le contraste
                        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                        enhanced = clahe.apply(gray)
                        
                        # Binarisation adaptative
                        binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                     cv2.THRESH_BINARY, 11, 2)
                        
                        # Agrandir pour améliorer OCR (facteur 4)
                        scale_factor = 4
                        binary_large = cv2.resize(binary, None, fx=scale_factor, fy=scale_factor, 
                                                interpolation=cv2.INTER_CUBIC)
                        
                        # Morphologie pour nettoyer
                        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                        binary_clean = cv2.morphologyEx(binary_large, cv2.MORPH_CLOSE, kernel)
                        
                        # **OCR avec configurations multiples**
                        ocr_configs = [
                            '--psm 8 -c tessedit_char_whitelist=0123456789',  # Mot simple, chiffres seulement
                            '--psm 7 -c tessedit_char_whitelist=0123456789',  # Ligne de texte
                            '--psm 13 -c tessedit_char_whitelist=0123456789', # Ligne brute
                            '--psm 6 -c tessedit_char_whitelist=0123456789'   # Bloc uniforme
                        ]
                        
                        for config in ocr_configs:
                            try:
                                text = pytesseract.image_to_string(binary_clean, config=config, timeout=3)
                                text_clean = text.strip()
                                
                                if text_clean:
                                    # Extraire numéros avec patterns multiples
                                    patterns = [
                                        r'\b(\d{1,4})\b',           # Numéros simples
                                        r'(\d{1,3}[-\.]\d{1,4})',   # Format XX-XXXX
                                        r'N[°o]?\s*(\d{1,4})',      # Format N° 1234
                                    ]
                                    
                                    for pattern in patterns:
                                        matches = re.findall(pattern, text_clean, re.IGNORECASE)
                                        if matches:
                                            number = matches[0] if isinstance(matches[0], str) else matches[0][0]
                                            
                                            # Valider le numéro
                                            if self._is_valid_artwork_number(number):
                                                logger.info(f"      🎯 OCR réussi: '{number}' (distance: {distance}px, config: {config[:10]})")
                                                
                                                # Sauvegarder les infos de l'OCR pour debug
                                                rectangle['ocr_attempts'] = ocr_attempts
                                                rectangle['ocr_distance'] = distance
                                                rectangle['ocr_zone_height'] = zone_height
                                                rectangle['ocr_config'] = config
                                                
                                                return number
                                            
                            except Exception as e:
                                logger.debug(f"OCR config failed: {e}")
                                continue
            
            # Aucun numéro trouvé après tous les tests
            logger.info(f"      ❌ OCR échoué après {ocr_attempts} tentatives")
            rectangle['ocr_attempts'] = ocr_attempts
            return None
            
        except Exception as e:
            logger.debug(f"Erreur OCR smart: {e}")
            return None
    
    def _is_valid_artwork_number(self, number_str):
        """Valide si un numéro trouvé peut être un numéro d'œuvre"""
        try:
            # Nettoyer le numéro
            clean_number = re.sub(r'[^\d]', '', str(number_str))
            
            # Doit contenir au moins un chiffre
            if not clean_number or not clean_number.isdigit():
                return False
            
            # Longueur raisonnable (1 à 4 chiffres)
            if len(clean_number) < 1 or len(clean_number) > 4:
                return False
            
            # Convertir en entier pour vérifications
            num_val = int(clean_number)
            
            # Éviter 0 et nombres trop grands
            if num_val == 0 or num_val > 9999:
                return False
            
            return True
            
        except:
            return False
    
    def ultra_detect_rectangles(self, image, config):
        """Détection ULTRA SENSIBLE de rectangles (même logique qu'avant)"""
        height, width = image.shape[:2]
        total_pixels = height * width
        
        # Prétraitement ULTRA selon le mode
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        sensitivity = config['sensitivity']
        mode = config['mode']
        min_area_div = config['min_area_div']
        
        if mode == 'documents':
            denoised = cv2.fastNlMeansDenoising(gray, h=15)
            clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(16,16))
            enhanced = clahe.apply(denoised)
            canny_low, canny_high = 2, 10
        elif mode == 'high_contrast':
            denoised = cv2.GaussianBlur(gray, (1, 1), 0)
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4,4))
            enhanced = clahe.apply(denoised)
            canny_low = max(5, sensitivity // 10)
            canny_high = max(15, sensitivity // 3)
        else:  # general
            denoised = cv2.bilateralFilter(gray, 5, 50, 50)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            canny_low = max(1, sensitivity // 20)
            canny_high = max(5, sensitivity // 5)
        
        # Détection de bords MULTI-MÉTHODES
        edges1 = cv2.Canny(enhanced, canny_low, canny_high)
        edges2 = cv2.Canny(enhanced, max(1, canny_low//2), max(3, canny_high//2))
        
        kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
        _, edges3 = cv2.threshold(gradient, sensitivity // 10, 255, cv2.THRESH_BINARY)
        
        edges4 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 7, 1)
        edges4 = cv2.bitwise_not(edges4)
        
        # Combiner toutes les méthodes
        combined = cv2.bitwise_or(edges1, edges2)
        combined = cv2.bitwise_or(combined, edges3)
        combined = cv2.bitwise_or(combined, edges4)
        
        # Morphologie minimale
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        
        # Contours
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        rectangles = []
        min_area = total_pixels / min_area_div
        
        for i, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
            area = cv2.contourArea(contour)
            
            if area < min_area:
                continue
            
            # Approximation très permissive
            epsilon_values = [0.001, 0.002, 0.005, 0.01, 0.02, 0.03]
            
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
            
            # Si pas de quadrilatère, essayer rectangle englobant
            if len(rectangles) == i:
                x, y, w, h = cv2.boundingRect(contour)
                bbox_area = w * h
                area_ratio = area / bbox_area if bbox_area > 0 else 0
                
                if area_ratio > 0.3:
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
            
            if len(rectangles) >= 50:
                break
        
        return rectangles
    
    def template_based_detection(self, image):
        """Détection basée sur des templates (même logique qu'avant)"""
        rectangles = []
        
        try:
            templates = []
            
            for w, h in [(100, 150), (150, 200), (200, 250), (80, 120), (60, 80)]:
                template = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(template, (5, 5), (w-5, h-5), 255, 2)
                templates.append(('rect', template))
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            for template_name, template in templates:
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= 0.3)
                
                for pt in zip(*locations[::-1]):
                    x, y = pt
                    w, h = template.shape[1], template.shape[0]
                    
                    rectangles.append({
                        'id': len(rectangles),
                        'corners': np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                        'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                        'area': w * h,
                        'method': f'template_{template_name}',
                        'confidence': 0.3
                    })
        
        except Exception as e:
            logger.debug(f"Template detection error: {e}")
        
        return rectangles[:10]
    
    def color_based_detection(self, image):
        """Détection basée sur l'analyse des couleurs (même logique qu'avant)"""
        rectangles = []
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Détection par variance locale
            kernel = np.ones((15, 15), np.float32) / 225
            mean_filtered = cv2.filter2D(gray.astype(np.float32), -1, kernel)
            variance = cv2.filter2D((gray.astype(np.float32) - mean_filtered) ** 2, -1, kernel)
            
            _, variance_thresh = cv2.threshold(variance.astype(np.uint8), 30, 255, cv2.THRESH_BINARY)
            
            # Détection par contraste local
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            contrast = np.sqrt(sobelx**2 + sobely**2)
            contrast_norm = ((contrast / contrast.max()) * 255).astype(np.uint8)
            _, contrast_thresh = cv2.threshold(contrast_norm, 50, 255, cv2.THRESH_BINARY)
            
            combined = cv2.bitwise_or(variance_thresh, contrast_thresh)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
            combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
            
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            min_area = (image.shape[0] * image.shape[1]) / 1500
            
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5:
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
    
    def _is_duplicate_rectangle(self, new_rect, existing_rects):
        """Vérifie si un rectangle est un doublon"""
        new_bbox = new_rect['bbox']
        new_x, new_y = new_bbox['x'], new_bbox['y']
        new_w, new_h = new_bbox['w'], new_bbox['h']
        
        for existing_rect in existing_rects:
            ex_bbox = existing_rect['bbox']
            ex_x, ex_y = ex_bbox['x'], ex_bbox['y']
            ex_w, ex_h = ex_bbox['w'], ex_bbox['h']
            
            left = max(new_x, ex_x)
            top = max(new_y, ex_y)
            right = min(new_x + new_w, ex_x + ex_w)
            bottom = min(new_y + new_h, ex_y + ex_h)
            
            if left < right and top < bottom:
                intersection = (right - left) * (bottom - top)
                area1 = new_w * new_h
                area2 = ex_w * ex_h
                
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
                'recommended_dpi': 400
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
        """Calcule le DPI optimal"""
        if area_mm2 < 30000:
            return 500
        elif area_mm2 < 70000:
            return 400
        elif area_mm2 < 150000:
            return 350
        else:
            return 300
    
    def extract_rectangle_image(self, image, rectangle):
        """Extrait l'image d'un rectangle avec correction automatique de rotation"""
        try:
            corners = rectangle['corners']
            if isinstance(corners, list):
                corners = np.array(corners, dtype=np.float32)
            
            # **NOUVELLE LOGIQUE : PRÉFÉRER BBOX POUR ÉVITER LES ROTATIONS**
            bbox = rectangle['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # Extraire d'abord avec bbox (pas de rotation)
            bbox_image = image[y:y+h, x:x+w].copy()
            
            # **VÉRIFICATION DE QUALITÉ DE L'EXTRACTION BBOX**
            if self._is_good_bbox_extraction(bbox_image, corners, (x, y, w, h)):
                logger.debug(f"      ✅ Extraction BBOX utilisée (évite rotation)")
                return bbox_image
            
            # **SINON : TRANSFORMATION DE PERSPECTIVE AVEC CORRECTION DE ROTATION**
            rect = self._order_points_smart(corners)
            (tl, tr, br, bl) = rect
            
            # Calculer les dimensions
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            
            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
            
            # Si dimensions trop petites, utiliser bbox
            if maxWidth < 30 or maxHeight < 30:
                logger.debug(f"      ⚠️ Dimensions trop petites, utilisation BBOX")
                return bbox_image
            
            # **DÉTECTER ET CORRIGER L'ORIENTATION**
            # Si la transformation donnerait une image plus haute que large
            # mais que le bbox original est plus large que haut, il y a probablement une rotation
            bbox_aspect = w / h if h > 0 else 1
            transform_aspect = maxWidth / maxHeight if maxHeight > 0 else 1
            
            # Si les ratios d'aspect sont très différents, préférer bbox
            aspect_diff = abs(bbox_aspect - transform_aspect) / max(bbox_aspect, transform_aspect)
            if aspect_diff > 0.5:  # Plus de 50% de différence
                logger.debug(f"      🔄 Rotation détectée (aspect diff: {aspect_diff:.2f}), utilisation BBOX")
                return bbox_image
            
            # **TRANSFORMATION DE PERSPECTIVE AVEC VÉRIFICATION**
            dst = np.array([
                [0, 0], [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]
            ], dtype="float32")
            
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
            
            # **VÉRIFICATION POST-TRANSFORMATION**
            if self._is_warped_image_rotated(warped, bbox_image):
                logger.debug(f"      🔄 Image transformée semble tournée, utilisation BBOX")
                return bbox_image
            
            logger.debug(f"      ✅ Transformation perspective OK")
            return warped
            
        except Exception as e:
            logger.error(f"Erreur extraction rectangle: {e}")
            # Fallback sur bbox
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
    
    def _order_points_smart(self, pts):
        """Ordonne les points intelligemment pour éviter les rotations"""
        try:
            # Convertir en numpy array si nécessaire
            if isinstance(pts, list):
                pts = np.array(pts, dtype=np.float32)
            
            # Calculer le centre
            center = np.mean(pts, axis=0)
            
            # Trier les points par angle depuis le centre (sens horaire)
            angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
            sorted_indices = np.argsort(angles)
            
            # Réorganiser pour avoir top-left, top-right, bottom-right, bottom-left
            sorted_pts = pts[sorted_indices]
            
            # Identifier le point le plus en haut à gauche comme référence
            top_left_idx = np.argmin(sorted_pts[:, 0] + sorted_pts[:, 1])
            
            # Réorganiser pour commencer par top-left
            ordered_pts = np.roll(sorted_pts, -top_left_idx, axis=0)
            
            return ordered_pts.astype(np.float32)
            
        except:
            # Fallback sur la méthode classique
            return self._order_points(pts)
    
    def _is_good_bbox_extraction(self, bbox_image, corners, bbox_coords):
        """Vérifie si l'extraction bbox est de bonne qualité"""
        try:
            x, y, w, h = bbox_coords
            
            # 1. Vérifier que l'image n'est pas trop petite
            if bbox_image.shape[0] < 20 or bbox_image.shape[1] < 20:
                return False
            
            # 2. Vérifier que les coins du contour sont proches du bbox
            corners_array = np.array(corners) if isinstance(corners, list) else corners
            
            # Points du bbox
            bbox_corners = np.array([
                [x, y], [x + w, y], [x + w, y + h], [x, y + h]
            ])
            
            # Calculer la distance moyenne entre les coins détectés et le bbox
            min_distances = []
            for corner in corners_array:
                distances = [np.linalg.norm(corner - bbox_corner) for bbox_corner in bbox_corners]
                min_distances.append(min(distances))
            
            avg_distance = np.mean(min_distances)
            max_allowed_distance = min(w, h) * 0.1  # 10% de la plus petite dimension
            
            # Si les coins sont proches du bbox, c'est bon
            return avg_distance <= max_allowed_distance
            
        except:
            return True  # En cas de doute, utiliser bbox
    
    def _is_warped_image_rotated(self, warped_image, bbox_image):
        """Détecte si l'image transformée est indésirément tournée"""
        try:
            # Comparer les ratios d'aspect
            warped_h, warped_w = warped_image.shape[:2]
            bbox_h, bbox_w = bbox_image.shape[:2]
            
            warped_aspect = warped_w / warped_h if warped_h > 0 else 1
            bbox_aspect = bbox_w / bbox_h if bbox_h > 0 else 1
            
            # Si les ratios sont inversés (l'un > 1, l'autre < 1), il y a rotation
            if (warped_aspect > 1.2 and bbox_aspect < 0.8) or (warped_aspect < 0.8 and bbox_aspect > 1.2):
                return True
            
            # Comparer les histogrammes pour voir si l'image est très différente
            warped_gray = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY) if len(warped_image.shape) == 3 else warped_image
            bbox_gray = cv2.cvtColor(bbox_image, cv2.COLOR_BGR2GRAY) if len(bbox_image.shape) == 3 else bbox_image
            
            # Redimensionner pour la comparaison
            size = (100, 100)
            warped_resized = cv2.resize(warped_gray, size)
            bbox_resized = cv2.resize(bbox_gray, size)
            
            # Calculer la corrélation
            correlation = cv2.matchTemplate(warped_resized, bbox_resized, cv2.TM_CCOEFF_NORMED)[0][0]
            
            # Si la corrélation est très faible, l'image est probablement tournée
            return correlation < 0.3
            
        except:
            return False  # En cas de doute, garder l'image transformée
    
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
        details_path = os.path.join(page_dir, "README_SMART.txt")
        
        content = f"""PAGE {page_result['page_number']} - EXTRACTION SMART QUALITY
{'=' * 60}

MODE: SMART QUALITY - Vérification qualité + OCR intelligent
- Statut: {'✅ Succès' if page_result['success'] else '❌ Échec'}
- Temps de traitement: {page_result['processing_time']}s
- Images extraites: {page_result['images_extracted']}
- Qualité OK: {page_result['quality_ok']}
- Qualité douteuse: {page_result['quality_doubtful']}
- Rectangles détectés: {page_result['rectangles_found']}
- DPI utilisé: {page_result.get('dpi_used', 'N/A')}

SEUIL DE QUALITÉ: {self.quality_threshold} (50%)

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

IMAGES EXTRAITES:
"""
        
        if page_result['images_saved']:
            for i, img_name in enumerate(page_result['images_saved'], 1):
                details = next((r for r in page_result.get('rectangles_details', []) 
                              if r['filename'] == img_name), {})
                
                quality_status = details.get('quality_status', 'N/A')
                quality_score = details.get('quality_score', 0)
                ocr_attempts = details.get('ocr_attempts', 0)
                
                content += f"""
{i:2d}. {img_name}
    - Numéro d'œuvre: {details.get('artwork_number', 'Aucun')}
    - Qualité: {quality_status} (score: {quality_score:.3f})
    - Taille: {details.get('size_kb', 0)} KB
    - Tentatives OCR: {ocr_attempts}
    - Méthode détection: {details.get('detection_method', 'N/A')}
    - Miniature: {details.get('thumbnail', 'N/A')}
"""
        else:
            content += "\nAucune image extraite.\n"
        
        if page_result.get('error'):
            content += f"\nERREUR:\n{page_result['error']}\n"
        
        content += f"""
MÉTHODES UTILISÉES:
✅ Détection ultra-sensible (5+ configs)
✅ Template matching
✅ Analyse de couleur et contraste
✅ Vérification de qualité automatique
✅ OCR par tâtonnement (5-50px, 4 hauteurs)
✅ Classification par qualité

FICHIERS DANS CE DOSSIER:
- README_SMART.txt (ce fichier)
- page_smart_details.json (données techniques)
- *.png (images qualité OK)
- DOUTEUX_*.png (images qualité douteuse)
- thumb_*.png (miniatures)

DOSSIERS DE QUALITÉ:
- ../qualite_OK/ (toutes les images de bonne qualité)
- ../qualite_DOUTEUSE/ (images à vérifier manuellement)

Extraction SMART effectuée le {page_result.get('start_time', 'N/A')}
"""
        
        with open(details_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def create_text_summary(self, global_log):
        """Crée un résumé texte global"""
        summary_path = os.path.join(self.session_dir, "RÉSUMÉ_SMART.txt")
        
        quality_stats = global_log.get('quality_stats', {})
        total_ok = quality_stats.get('total_ok', 0)
        total_doubtful = quality_stats.get('total_doubtful', 0)
        quality_ratio = quality_stats.get('quality_ratio', 0)
        
        content = f"""EXTRACTION PDF SMART QUALITY - RÉSUMÉ COMPLET
{'=' * 70}

🎯 MODE SMART QUALITY - Vérification qualité + OCR intelligent

FICHIER SOURCE:
- Nom: {global_log['pdf_name']}
- Chemin: {global_log['pdf_path']}

EXTRACTION SMART:
- Début: {global_log['start_time']}
- Fin: {global_log['end_time']}
- Durée totale: {self._calculate_duration(global_log['start_time'], global_log['end_time'])}

RÉSULTATS SMART:
- Pages traitées: {global_log['total_pages']}
- Pages réussies: {global_log['success_pages']}
- Pages échouées: {global_log['failed_pages']}
- Images extraites: {global_log['total_images_extracted']}

QUALITÉ DES EXTRACTIONS:
- Images qualité OK: {total_ok} ({quality_ratio:.1%})
- Images douteuses: {total_doubtful}
- Seuil de qualité: {global_log['quality_threshold']} (50%)

DÉTAIL PAR PAGE:
"""
        
        for page in global_log['pages']:
            status = "✅" if page['success'] else "❌"
            content += f"  Page {page['page_number']:3d}: {status} {page['images_extracted']:2d} images "
            content += f"(OK:{page.get('quality_ok', 0)}, Douteux:{page.get('quality_doubtful', 0)}) "
            content += f"({page['processing_time']:4.1f}s)\n"
        
        content += f"""
TECHNOLOGIES SMART UTILISÉES:
🔬 Multi-détection ultra-sensible
🎯 Template matching intelligent
🌈 Analyse de couleur et contraste
📊 Évaluation automatique de qualité
🔍 OCR par tâtonnement (distances 5-50px)
🧠 Classification automatique par qualité
🚫 Déduplication avancée

ORGANISATION DES FICHIERS:
- Dossier principal: {os.path.basename(self.session_dir)}
- Structure: page_XXX/ (détails par page)
- qualite_OK/ (images de bonne qualité)
- qualite_DOUTEUSE/ (images à vérifier)

FICHIERS GLOBAUX:
- RÉSUMÉ_SMART.txt (ce fichier)
- extraction_smart_complete.json (log technique complet)

🎉 RÉSULTAT: {global_log['total_images_extracted']} images extraites avec contrôle qualité !
   {total_ok} images validées automatiquement, {total_doubtful} à vérifier manuellement.

💡 CONSEIL: Vérifiez le dossier 'qualite_DOUTEUSE' pour les images de qualité incertaine.
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
    print("🚀 EXTRACTEUR PDF SMART QUALITY")
    print("=" * 60)
    print("🎯 MODE SMART : Vérification qualité + OCR intelligent")
    print("📊 Seuil qualité 50% + OCR par tâtonnement")
    print("🗂️ Classification automatique par qualité")
    print("=" * 60)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Demander le nombre de pages (optionnel)
    max_pages_input = input("📄 Nombre max de pages (Entrée = toutes): ").strip()
    max_pages = None
    if max_pages_input and max_pages_input.isdigit():
        max_pages = int(max_pages_input)
    
    # Créer l'extracteur SMART
    extractor = SmartQualityPDFExtractor()
    
    # Lancer l'extraction SMART
    print("\n🚀 Extraction SMART en cours...")
    print("📊 Vérification qualité automatique (seuil 50%)")
    print("🔍 OCR par tâtonnement (distances 5-50px)")
    print("🗂️ Classification par qualité")
    
    success = extractor.extract_pdf(pdf_path, max_pages)
    
    if success:
        print("\n✅ Extraction SMART terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Vérifiez les dossiers qualite_OK/ et qualite_DOUTEUSE/")
    else:
        print("\n❌ Extraction SMART échouée!")


if __name__ == "__main__":
    main()
