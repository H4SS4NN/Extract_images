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
    
    def extract_pdf(self, pdf_path, max_pages=None):
        """Extraction complète ULTRA SENSIBLE d'un PDF"""
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
                total_pages = len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"❌ Impossible de lire le PDF: {e}")
            return False
        
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        logger.info(f"📄 {total_pages} pages à traiter en mode ULTRA")
        
        # Créer le fichier de résumé global
        global_log = {
            'pdf_name': pdf_name,
            'pdf_path': pdf_path,
            'session_dir': self.session_dir,
            'mode': 'ULTRA_SENSIBLE',
            'start_time': datetime.now().isoformat(),
            'total_pages': total_pages,
            'pages': []
        }
        
        # Traiter chaque page
        for page_num in range(1, total_pages + 1):
            logger.info(f"📄 Traitement ULTRA page {page_num}/{total_pages}")
            
            page_result = self.process_page_ultra(pdf_path, page_num)
            global_log['pages'].append(page_result)
            
            if page_result['success']:
                self.total_extracted += page_result['images_extracted']
                logger.info(f"  ✅ Page {page_num}: {page_result['images_extracted']} images capturées")
        
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
            
            # Utiliser TOUS les rectangles trouvés (fusion des méthodes)
            final_rectangles = all_rectangles
            page_result['rectangles_found'] = len(final_rectangles)
            page_result['rectangles_details'] = []
            
            logger.info(f"  🎯 TOTAL FINAL: {len(final_rectangles)} rectangles uniques détectés")
            
            # Extraire et sauvegarder chaque rectangle
            for rect_idx, rectangle in enumerate(final_rectangles):
                try:
                    # Extraire l'image
                    extracted_image = self.extract_rectangle_image(page_cv, rectangle)
                    if extracted_image is None:
                        continue
                    
                    # Filtrer les images trop petites (mais seuil très bas)
                    if extracted_image.shape[0] < 20 or extracted_image.shape[1] < 20:
                        logger.info(f"      ⚠️ Rectangle {rect_idx+1} trop petit: {extracted_image.shape}")
                        continue
                    
                    # Détecter le numéro d'œuvre si possible
                    artwork_number = self.detect_artwork_number(page_cv, rectangle)
                    
                    # Déterminer le nom de fichier
                    if artwork_number:
                        filename = f"oeuvre_{artwork_number}.png"
                    else:
                        filename = f"rectangle_{rect_idx + 1:02d}.png"
                    
                    # Sauvegarder
                    image_path = os.path.join(page_dir, filename)
                    cv2.imwrite(image_path, extracted_image)
                    
                    # Créer une miniature
                    thumbnail = self.create_thumbnail(extracted_image)
                    thumb_path = os.path.join(page_dir, f"thumb_{filename}")
                    cv2.imwrite(thumb_path, thumbnail)
                    
                    # Enregistrer les détails
                    rect_details = {
                        'rectangle_id': rect_idx + 1,
                        'filename': filename,
                        'artwork_number': artwork_number,
                        'bbox': rectangle.get('bbox'),
                        'area': rectangle.get('area'),
                        'size_kb': os.path.getsize(image_path) // 1024,
                        'thumbnail': f"thumb_{filename}",
                        'detection_method': rectangle.get('method', 'unknown'),
                        'confidence': rectangle.get('confidence', 0.5)
                    }
                    
                    page_result['rectangles_details'].append(rect_details)
                    page_result['images_saved'].append(filename)
                    page_result['images_extracted'] += 1
                    
                    logger.info(f"    ✅ Sauvé: {filename} ({extracted_image.shape[1]}×{extracted_image.shape[0]})")
                    
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
    
    def _is_duplicate_rectangle(self, new_rect, existing_rects):
        """Vérifie si un rectangle est un doublon"""
        new_bbox = new_rect['bbox']
        new_x, new_y = new_bbox['x'], new_bbox['y']
        new_w, new_h = new_bbox['w'], new_bbox['h']
        
        for existing_rect in existing_rects:
            ex_bbox = existing_rect['bbox']
            ex_x, ex_y = ex_bbox['x'], ex_bbox['y']
            ex_w, ex_h = ex_bbox['w'], ex_bbox['h']
            
            # Calculer le chevauchement
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
        """Extrait l'image d'un rectangle"""
        try:
            corners = rectangle['corners']
            if isinstance(corners, list):
                corners = np.array(corners, dtype=np.float32)
            
            # Transformation de perspective
            rect = self._order_points(corners)
            (tl, tr, br, bl) = rect
            
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            
            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
            
            # Éviter les dimensions nulles
            if maxWidth < 10 or maxHeight < 10:
                bbox = rectangle['bbox']
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                return image[y:y+h, x:x+w]
            
            dst = np.array([
                [0, 0], [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]
            ], dtype="float32")
            
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
            
            # Si trop petit après transformation, utiliser bbox
            if warped.shape[0] < 30 or warped.shape[1] < 30:
                bbox = rectangle['bbox']
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                warped = image[y:y+h, x:x+w]
            
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
    
    def detect_artwork_number(self, image, rectangle):
        """Détecte le numéro d'œuvre (OCR simplifié)"""
        try:
            # Vérifier si Tesseract est disponible
            if not hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
                return None
            
            bbox = rectangle['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # Chercher dans plusieurs zones autour du rectangle
            search_zones = [
                (x, y + h + 5, w, 80),      # Sous le rectangle
                (x - 50, y + h//2, 100, 60), # À gauche
                (x + w + 5, y + h//2, 100, 60), # À droite
            ]
            
            for sx, sy, sw, sh in search_zones:
                if (sx >= 0 and sy >= 0 and 
                    sx + sw < image.shape[1] and sy + sh < image.shape[0]):
                    
                    search_zone = image[sy:sy+sh, sx:sx+sw]
                    
                    # Prétraitement OCR
                    gray = cv2.cvtColor(search_zone, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    # Agrandir pour améliorer OCR
                    binary = cv2.resize(binary, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                    
                    # OCR
                    text = pytesseract.image_to_string(binary, config='--psm 8 -c tessedit_char_whitelist=0123456789')
                    
                    # Extraire numéros
                    numbers = re.findall(r'\b\d{1,4}\b', text.strip())
                    if numbers:
                        return numbers[0]
            
            return None
            
        except Exception:
            return None
    
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
✅ Seuils ultra-permissifs
✅ DPI élevé pour plus de précision
✅ Fusion intelligente des résultats

FICHIERS DANS CE DOSSIER:
- README_ULTRA.txt (ce fichier)
- page_ultra_details.json (données techniques complètes)
- *.png (images extraites)
- thumb_*.png (miniatures 200px)

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
            content += f"  Page {page['page_number']:3d}: {status} {page['images_extracted']:2d} images "
            content += f"({page['processing_time']:4.1f}s) - {page.get('best_config', 'N/A')}\n"
        
        content += f"""
TECHNOLOGIES ULTRA UTILISÉES:
🔬 Multi-détection (5+ algorithmes par page)
🎯 Template matching intelligent
🌈 Analyse de couleur et contraste
📐 Seuils ultra-permissifs
🔍 DPI élevé (400+ par page)
🧠 Fusion intelligente des résultats
🚫 Déduplication avancée

ORGANISATION DES FICHIERS:
- Dossier principal: {os.path.basename(self.session_dir)}
- Structure: page_XXX/
  ├── README_ULTRA.txt (détails de la page)
  ├── page_ultra_details.json (données techniques)
  ├── *.png (images extraites)
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
    print("🔬 5+ algorithmes par page, fusion intelligente")
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
    
    # Créer l'extracteur ULTRA
    extractor = UltraSensitivePDFExtractor()
    
    # Lancer l'extraction ULTRA
    print("\n🚀 Extraction ULTRA en cours...")
    print("⚡ Chaque page testée avec 5+ méthodes différentes")
    print("🔬 Seuils ultra-permissifs, DPI élevé")
    
    success = extractor.extract_pdf(pdf_path, max_pages)
    
    if success:
        print("\n✅ Extraction ULTRA terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Mode ULTRA: Toutes les images devraient être capturées !")
    else:
        print("\n❌ Extraction ULTRA échouée!")


if __name__ == "__main__":
    main()
