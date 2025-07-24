import os
import io
import cv2
import numpy as np
import zipfile
import tempfile
import uuid
import re
import logging
import time
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename
import pytesseract
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Tesseract OCR - chemins Windows communs
def configure_tesseract():
    """Configure pytesseract pour trouver l'exécutable Tesseract"""
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
    
    logger.warning("⚠️ Tesseract non trouvé dans les emplacements standards")
    return False

# Configurer Tesseract au démarrage
configure_tesseract()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'pdf'}

# Créer les dossiers nécessaires
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_pdf(filename):
    return filename.lower().endswith('.pdf')

class OCRDetector:
    """Détecteur d'OCR existant dans les PDF"""
    
    def __init__(self):
        self.min_text_ratio = 0.1  # Minimum 10% de pages avec texte pour considérer qu'il y a de l'OCR
    
    def has_existing_ocr(self, pdf_path):
        """
        Détecte si un PDF contient déjà de l'OCR/texte extractible
        Retourne: {has_ocr: bool, text_pages: int, total_pages: int, confidence: float}
        """
        try:
            logger.info(f"🔍 Vérification OCR existant dans {pdf_path} (analyse rapide - 3 pages max)")
            start_time = time.time()
            
            # Méthode 1: PyPDF2 (rapide)
            text_pages_pypdf2 = 0
            total_pages = 0
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                # Échantillonner très peu de pages pour test rapide
                sample_size = min(3, total_pages)  # Maximum 3 pages seulement !
                sample_indices = [0, 1, 2] if total_pages >= 3 else list(range(total_pages))
                
                for i in sample_indices:
                    try:
                        logger.info(f"🔍 Test OCR page {i+1}...")
                        page = pdf_reader.pages[i]
                        text = page.extract_text().strip()
                        logger.info(f"📝 Page {i+1}: {len(text)} caractères extraits")
                        if len(text) > 50:  # Au moins 50 caractères
                            text_pages_pypdf2 += 1
                            logger.info(f"✅ Page {i+1}: Texte détecté !")
                        else:
                            logger.info(f"❌ Page {i+1}: Pas de texte significatif")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur extraction page {i+1}: {e}")
                        continue
            
            # Extrapoler le résultat à tout le document (estimation conservative)
            if sample_size > 0 and text_pages_pypdf2 > 0:
                # Si au moins 1 page sur 3 a du texte, on estime que c'est bon
                text_pages_pypdf2 = int((text_pages_pypdf2 / sample_size) * total_pages)
            else:
                text_pages_pypdf2 = 0
            
            # Méthode 2: pdfplumber (plus précise mais plus lente)
            text_pages_plumber = 0
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # Seulement les 2 premières pages avec pdfplumber (plus rapide)
                    for i in sample_indices[:2]:  # Max 2 pages avec pdfplumber
                        try:
                            if i < len(pdf.pages):
                                page = pdf.pages[i]
                                text = page.extract_text()
                                if text and len(text.strip()) > 50:
                                    text_pages_plumber += 1
                        except Exception:
                            continue
                
                # Extrapoler (estimation conservative)
                if len(sample_indices) > 0 and text_pages_plumber > 0:
                    text_pages_plumber = int((text_pages_plumber / min(2, len(sample_indices))) * total_pages)
                else:
                    text_pages_plumber = 0
                    
            except Exception as e:
                logger.warning(f"⚠️ pdfplumber échoué: {e}")
                text_pages_plumber = text_pages_pypdf2  # Fallback
            
            # Combiner les résultats (prendre le maximum)
            text_pages = max(text_pages_pypdf2, text_pages_plumber)
            text_ratio = text_pages / total_pages if total_pages > 0 else 0
            
            has_ocr = text_ratio >= self.min_text_ratio
            confidence = min(1.0, text_ratio * 2)  # Confiance basée sur le ratio
            
            analysis_time = time.time() - start_time
            logger.info(f"📄 OCR Analysis (échantillon {sample_size} pages): {text_pages}/{total_pages} pages estimées avec texte ({text_ratio:.1%})")
            logger.info(f"🤖 OCR existant: {'OUI' if has_ocr else 'NON'} (confiance: {confidence:.1%}) - Analyse rapide terminée en {analysis_time:.2f}s !")
            
            return {
                'has_ocr': has_ocr,
                'text_pages': text_pages,
                'total_pages': total_pages,
                'text_ratio': text_ratio,
                'confidence': confidence,
                'recommendation': self._get_recommendation(has_ocr, text_ratio, total_pages)
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur détection OCR: {str(e)}")
            return {
                'has_ocr': False,
                'text_pages': 0,
                'total_pages': 0,
                'text_ratio': 0.0,
                'confidence': 0.0,
                'recommendation': 'Impossible de détecter l\'OCR - traitement normal recommandé',
                'error': str(e)
            }
    
    def _get_recommendation(self, has_ocr, text_ratio, total_pages):
        """Génère une recommandation basée sur l'analyse OCR"""
        if has_ocr:
            if text_ratio > 0.8:
                return f"✅ OCR complet détecté ({text_ratio:.1%}) - Extraction directe recommandée"
            elif text_ratio > 0.5:
                return f"⚠️ OCR partiel détecté ({text_ratio:.1%}) - Vérification manuelle recommandée"
            else:
                return f"🔄 OCR limité détecté ({text_ratio:.1%}) - Re-traitement peut améliorer"
        else:
            if total_pages > 50:
                return f"🚀 Aucun OCR détecté sur {total_pages} pages - Traitement IA recommandé (temps estimé: {total_pages * 3}s)"
            else:
                return f"🔍 Aucun OCR détecté - Traitement IA recommandé"

class ProgressTracker:
    """Suivi de progression pour traitement long"""
    
    def __init__(self, total_items, operation_name="Traitement"):
        self.total_items = total_items
        self.current_item = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_update = self.start_time
        
    def update(self, current_item, item_name=""):
        """Met à jour la progression et émet via SocketIO"""
        self.current_item = current_item
        current_time = time.time()
        
        # Calculer les métriques
        progress_ratio = current_item / self.total_items if self.total_items > 0 else 0
        elapsed_time = current_time - self.start_time
        
        # Estimer le temps restant
        if current_item > 0 and progress_ratio > 0:
            estimated_total_time = elapsed_time / progress_ratio
            remaining_time = estimated_total_time - elapsed_time
        else:
            remaining_time = 0
        
        # Calculer la vitesse
        items_per_second = current_item / elapsed_time if elapsed_time > 0 else 0
        
        progress_data = {
            'current': current_item,
            'total': self.total_items,
            'progress_percent': round(progress_ratio * 100, 1),
            'elapsed_time': round(elapsed_time, 1),
            'remaining_time': round(remaining_time, 1),
            'items_per_second': round(items_per_second, 2),
            'operation': self.operation_name,
            'current_item_name': item_name,
            'eta_formatted': self._format_time(remaining_time),
            'elapsed_formatted': self._format_time(elapsed_time)
        }
        
        # Émettre via SocketIO
        try:
            socketio.emit('progress_update', progress_data)
            logger.info(f"📊 WebSocket émis: {progress_data}")
        except Exception as e:
            logger.error(f"❌ Erreur WebSocket emit: {e}")
        
        logger.info(f"📊 {self.operation_name}: {current_item}/{self.total_items} ({progress_ratio:.1%}) - ETA: {self._format_time(remaining_time)}")
        
    def _format_time(self, seconds):
        """Formate le temps en format lisible"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

class PDFProcessor:
    def __init__(self):
        self.pages = []
        self.pdf_rectangles = []
        self.original_filename = None  # Nouveau: stocker le nom original
        
    def clear(self):
        """Nettoyer les données PDF précédentes"""
        self.pages = []
        self.pdf_rectangles = []
        self.original_filename = None

    def process_pdf(self, pdf_path, detector, sensitivity=50, mode='general', skip_ocr_detection=False):
        """
        Traite un PDF page par page et détecte les rectangles avec progression en temps réel
        """
        try:
            # Stocker le nom original (sans extension)
            import os
            self.original_filename = os.path.splitext(os.path.basename(pdf_path))[0]
            logger.info(f"📄 Traitement PDF: {self.original_filename}")
            
            # **ÉTAPE 1: L'analyse OCR a déjà été faite dans /upload**
            # On arrive ici seulement si aucun OCR ou choix utilisateur = IA
            logger.info("🚀 Traitement IA démarré (OCR déjà analysé)")
            
            # **ÉTAPE 2: Obtenir le nombre de pages d'abord**
            logger.info("🔍 Comptage des pages du PDF...")
            
            # Obtenir le nombre de pages rapidement avec PyPDF2
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)
            except Exception as e:
                logger.warning(f"⚠️ Impossible de compter les pages: {e}")
                total_pages = 100  # Estimation par défaut
            
            logger.info(f"📄 PDF détecté: {total_pages} pages")
            
            # **ÉTAPE 3: TRAITEMENT PROGRESSIF PAGE PAR PAGE** 
            logger.info("🚀 NOUVEAU: Traitement progressif avec résultats immédiats !")
            logger.info(f"📄 Configuration QUALITÉ MAXIMALE - DPI 600 pour extraction premium")
            
            socketio.emit('progressive_start', {
                'total_pages': total_pages,
                'message': 'Traitement progressif démarré - Premiers résultats dans 30-60 secondes !',
                'quality': 'ULTRA HAUTE (DPI 600)'
            })
            
            # **ÉTAPE 4: Initialiser le tracker de progression**
            progress_tracker = ProgressTracker(total_pages, f"Traitement progressif PDF ({total_pages} pages)")
            
            self.pages = []
            self.pdf_rectangles = []
            
            # **ÉTAPE 5: TRAITEMENT PAGE PAR PAGE AVEC RÉSULTATS IMMÉDIATS**
            for page_num in range(1, total_pages + 1):
                page_start_time = time.time()
                
                # Mettre à jour la progression
                progress_tracker.update(page_num, f"Page {page_num}")
                
                logger.info(f"🔄 Page {page_num}/{total_pages}: Conversion + Traitement...")
                
                # **1. CONVERTIR SEULEMENT CETTE PAGE (QUALITÉ MAX)**
                socketio.emit('page_processing', {
                    'current_page': page_num,
                    'total_pages': total_pages,
                    'page_name': f"Page {page_num}",
                    'stage': 'conversion'
                })
                
                try:
                    # Convertir SEULEMENT cette page en ultra haute qualité
                    page_images = convert_from_path(
                        pdf_path, 
                        dpi=600,  # ULTRA HAUTE QUALITÉ
                        first_page=page_num,
                        last_page=page_num
                    )
                    
                    if not page_images:
                        logger.warning(f"⚠️ Page {page_num}: Conversion échouée")
                        continue
                        
                    page_image = page_images[0]
                    
                except Exception as e:
                    logger.error(f"❌ Page {page_num}: Erreur conversion - {e}")
                    continue
                
                # **2. TRAITER IMMÉDIATEMENT CETTE PAGE**
                socketio.emit('page_processing', {
                    'current_page': page_num,
                    'total_pages': total_pages,
                    'page_name': f"Page {page_num}",
                    'stage': 'detection'
                })
                
                # Convertir PIL vers OpenCV
                page_array = np.array(page_image)
                page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
                
                # Stocker l'image de la page
                page_data = {
                    'page_number': page_num,
                    'image': page_cv
                }
                self.pages.append(page_data)
                
                # Détecter les rectangles sur cette page
                rectangles = detector.detect_rectangles(page_cv, sensitivity, mode)
                
                # **CONVERTIR TOUS LES ARRAYS NUMPY EN LISTES POUR LA SÉRIALISATION JSON**
                for rect in rectangles:
                    # Convertir corners (array NumPy vers liste)
                    if 'corners' in rect:
                        if hasattr(rect['corners'], 'tolist'):
                            rect['corners'] = rect['corners'].tolist()
                    
                    # Convertir bbox (tuple vers dict)
                    if 'bbox' in rect:
                        if isinstance(rect['bbox'], tuple):
                            x, y, w, h = rect['bbox']
                            rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                    
                    # Supprimer le contour (pas sérialisable)
                    if 'contour' in rect:
                        del rect['contour']
                    
                    # Convertir tous les autres arrays NumPy possibles
                    for key, value in rect.items():
                        if hasattr(value, 'tolist'):
                            rect[key] = value.tolist()
                        elif hasattr(value, 'item'):  # Scalaires NumPy
                            rect[key] = value.item()
                
                # Stocker les résultats pour cette page
                page_result = {
                    'page_number': page_num,
                    'rectangles': rectangles,
                    'rectangles_count': len(rectangles)
                }
                self.pdf_rectangles.append(page_result)
                
                page_time = time.time() - page_start_time
                logger.info(f"✅ Page {page_num}: {len(rectangles)} rectangles détectés en {page_time:.1f}s")
                
                # **3. ENVOYER LES RÉSULTATS DE CETTE PAGE IMMÉDIATEMENT !**
                socketio.emit('page_results', {
                    'page_number': page_num,
                    'rectangles': rectangles,
                    'rectangles_count': len(rectangles),
                    'processing_time': page_time,
                    'progress_percent': (page_num / total_pages) * 100,
                    'message': f"Page {page_num} terminée - {len(rectangles)} rectangles trouvés"
                })
                
                logger.info(f"📤 Résultats page {page_num} envoyés au frontend")
            
            # **ÉTAPE 6: Finalisation**
            progress_tracker.update(total_pages, "Finalisation...")
            
            # Calculer le total
            total_rectangles = sum(page['rectangles_count'] for page in self.pdf_rectangles)
            
            logger.info(f"🎉 PDF traité: {total_pages} pages, {total_rectangles} rectangles au total")
            
            # Émettre la completion
            socketio.emit('processing_complete', {
                'total_pages': total_pages,
                'total_rectangles': total_rectangles,
                'filename': self.original_filename
            })
            
            result = {
                'success': True,
                'total_pages': total_pages,
                'total_rectangles': total_rectangles,
                'pages': self.pdf_rectangles,
                'filename': self.original_filename,
                'is_pdf': True,
                'ocr_info': ocr_info  # Inclure les infos OCR
            }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement PDF: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            # Émettre l'erreur
            socketio.emit('processing_error', {
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            
            return {
                'success': False,
                'error': str(e)
            }

pdf_processor = PDFProcessor()
ocr_detector = OCRDetector()

class RectangleDetector:
    def __init__(self):
        self.rectangles = []
        
    def order_points(self, pts):
        """Ordonner les points dans l'ordre : top-left, top-right, bottom-right, bottom-left"""
        # Initialiser une liste de coordonnées qui sera ordonnée
        # de telle sorte que le premier élément de la liste soit le top-left,
        # le deuxième élément soit le top-right, le troisième soit le bottom-right,
        # et le quatrième soit le bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        
        # Le point top-left aura la plus petite somme, tandis que le
        # point bottom-right aura la plus grande somme
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        # Le point top-right aura la plus petite différence,
        # tandis que le point bottom-left aura la plus grande différence
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def four_point_transform(self, image, pts):
        """Appliquer une transformation de perspective à partir de 4 points"""
        # Obtenir une représentation cohérente des points et dégrouper
        # les coordonnées individuelles
        rect = self.order_points(pts)
        (tl, tr, br, bl) = rect
        
        # Calculer la largeur de la nouvelle image, qui sera la
        # distance maximale entre bottom-right et bottom-left
        # x-coordonnées ou top-right et top-left x-coordonnées
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        # Calculer la hauteur de la nouvelle image, qui sera la
        # distance maximale entre top-right et bottom-right
        # y-coordonnées ou top-left et bottom-left y-coordonnées
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        # Construire l'ensemble de points de destination pour obtenir une vue "bird's eye"
        # (vue du dessus) de l'image, en spécifiant à nouveau les points
        # dans l'ordre top-left, top-right, bottom-right et bottom-left
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        # Calculer la matrice de transformation de perspective et l'appliquer
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
    def detect_rectangles(self, image, sensitivity=50, mode='general'):
        """Méthode principale de détection avec différents modes"""
        logger.info(f"🔍 Mode: {mode}, Sensibilité: {sensitivity}")
        
        try:
            # Prétraitement adaptatif selon le mode
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # **ADAPTATION SELON LE MODE**
            if mode == 'documents':
                # Mode spécialisé pour documents multiples (blanc/blanc)
                denoised = cv2.fastNlMeansDenoising(gray, h=10)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16,16))
                enhanced = clahe.apply(denoised)
                canny_low = 5
                canny_high = 20
                min_area_divisor = 400
            elif mode == 'high_contrast':
                # Mode pour objets bien contrastés
                denoised = cv2.GaussianBlur(gray, (3, 3), 0)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = clahe.apply(denoised)
                canny_low = max(30, sensitivity // 2)
                canny_high = max(80, sensitivity * 2)
                min_area_divisor = 100
            else:  # mode general
                denoised = cv2.fastNlMeansDenoising(gray)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                enhanced = clahe.apply(denoised)
                canny_low = max(10, sensitivity // 2)
                canny_high = max(30, sensitivity)
                min_area_divisor = 200
            
            # Détection de bords et combinaison de techniques
            edges_sensitive = cv2.Canny(enhanced, canny_low, canny_high)
            
            # Gradient morphologique
            kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
            _, gradient_thresh = cv2.threshold(gradient, sensitivity // 4, 255, cv2.THRESH_BINARY)
            
            # Seuillage adaptatif
            block_size = 15 if mode == 'documents' else 11
            adaptive_thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, block_size, 2
            )
            adaptive_thresh = cv2.bitwise_not(adaptive_thresh)
            
            # Combiner toutes les techniques
            combined = cv2.bitwise_or(edges_sensitive, gradient_thresh)
            combined = cv2.bitwise_or(combined, adaptive_thresh)
            
            # Morphologie adaptée
            if mode == 'documents':
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=2)
            else:
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close)
            
            # Détection des contours
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            logger.info(f"Contours trouvés: {len(contours)}")
            
            if not contours:
                logger.warning("Aucun contour détecté")
                return []
            
            # Filtrage et approximation des rectangles
            rectangles = []
            min_area = (image.shape[0] * image.shape[1]) / min_area_divisor
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                if area < min_area:
                    continue
                
                # Approximation progressive
                epsilon_steps = [0.003, 0.005, 0.008, 0.012, 0.015] if mode == 'documents' else [0.005, 0.01, 0.015, 0.02, 0.025]
                
                for epsilon_mult in epsilon_steps:
                    epsilon = epsilon_mult * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    if len(approx) == 4 and cv2.isContourConvex(approx):
                        rectangles.append({
                            'id': len(rectangles),
                            'contour': contour,
                            'corners': approx.reshape(4, 2),
                            'area': area,
                            'bbox': cv2.boundingRect(contour),
                            'mode': mode
                        })
                        break
                else:
                    # Fallback rectangle englobant
                    x, y, w, h = cv2.boundingRect(contour)
                    bbox_area = w * h
                    area_ratio = area / bbox_area if bbox_area > 0 else 0
                    ratio_threshold = 0.5 if mode == 'documents' else 0.6
                    
                    if area_ratio > ratio_threshold:
                        corners = np.array([
                            [x, y], [x + w, y], [x + w, y + h], [x, y + h]
                        ])
                        
                        rectangles.append({
                            'id': len(rectangles),
                            'contour': contour,
                            'corners': corners,
                            'area': area,
                            'bbox': (x, y, w, h),
                            'is_bounding_box': True,
                            'confidence': area_ratio,
                            'mode': mode
                        })
                
                max_rectangles = 20 if mode == 'documents' else 15
                if len(rectangles) >= max_rectangles:
                    break
            
            # Filtrage des chevauchements
            rectangles = self.filter_overlapping_rectangles(rectangles)
            logger.info(f"✅ {len(rectangles)} rectangles détectés")
            
            # **NOUVEAU: Détection des numéros d'œuvre**
            if rectangles:
                logger.info("🎨 Lancement détection numéros d'œuvre...")
                
                # **CONVERTIR BBOX DE TUPLE VERS DICT AVANT OCR**
                for rect in rectangles:
                    if 'bbox' in rect and isinstance(rect['bbox'], tuple):
                        x, y, w, h = rect['bbox']
                        rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                        logger.debug("  Bbox converti pour OCR")
                
                try:
                    rectangles = artwork_detector.detect_artwork_numbers(image, rectangles)
                except Exception as ocr_error:
                    logger.error(f"⚠️ Erreur OCR (continuons sans numéros): {str(ocr_error)}")
                    # Continuer sans les numéros en cas d'erreur OCR
                    for rect in rectangles:
                        rect['artwork_number'] = None
            
            return rectangles
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection: {str(e)}")
            return []
    
    def filter_overlapping_rectangles(self, rectangles):
        """Filtrer les rectangles qui se chevauchent trop (doublons)"""
        if len(rectangles) <= 1:
            return rectangles
        
        filtered = []
        
        for i, rect1 in enumerate(rectangles):
            is_duplicate = False
            x1, y1, w1, h1 = rect1['bbox']
            
            for j, rect2 in enumerate(filtered):
                x2, y2, w2, h2 = rect2['bbox']
                
                # Calculer l'intersection
                left = max(x1, x2)
                top = max(y1, y2)
                right = min(x1 + w1, x2 + w2)
                bottom = min(y1 + h1, y2 + h2)
                
                if left < right and top < bottom:
                    intersection_area = (right - left) * (bottom - top)
                    area1 = w1 * h1
                    area2 = w2 * h2
                    
                    # Si l'intersection représente plus de 50% de l'une des deux zones
                    overlap_ratio1 = intersection_area / area1
                    overlap_ratio2 = intersection_area / area2
                    
                    if overlap_ratio1 > 0.5 or overlap_ratio2 > 0.5:
                        # Garder le plus grand
                        if area1 <= area2:
                            is_duplicate = True
                            break
                        else:
                            # Remplacer l'ancien par le nouveau (plus grand)
                            filtered[j] = rect1
                            is_duplicate = True
                            break
            
            if not is_duplicate:
                filtered.append(rect1)
        
        return filtered
    
    def extract_rectangle(self, image, rectangle):
        """Extraire et redresser un rectangle"""
        corners = rectangle['corners']
        
        # Appliquer la transformation de perspective
        warped = self.four_point_transform(image, corners)
        
        # Si l'image est trop petite après transformation, on garde l'original
        if warped.shape[0] < 50 or warped.shape[1] < 50:
            x, y, w, h = rectangle['bbox']
            warped = image[y:y+h, x:x+w]
        
        return warped
    
    def create_preview_with_corners(self, original_image, rectangle):
        """Créer une prévisualisation montrant les coins détectés"""
        preview = original_image.copy()
        corners = rectangle['corners']
        
        # Dessiner le contour du rectangle
        cv2.drawContours(preview, [corners.astype(np.int32)], -1, (0, 255, 0), 3)
        
        # Dessiner les coins
        for i, corner in enumerate(corners):
            cv2.circle(preview, tuple(corner.astype(int)), 8, (255, 0, 0), -1)
            cv2.putText(preview, str(i+1), tuple(corner.astype(int) + 15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return preview

class ArtworkNumberDetector:
    """Détecteur de numéros d'œuvre par OCR intelligent"""
    
    def __init__(self):
        self.number_patterns = [
            r'\b\d{1,6}\b',           # Numéros simples (1-6 chiffres)
            r'\b\d{1,3}[-\.]\d{1,4}\b', # Format XX-XXXX ou XX.XXXX
            r'\b[A-Z]{1,3}[-\.]\d{1,4}\b', # Format ABC-1234
            r'\bN[°o]\s*\d{1,6}\b',   # Format N° 1234
            r'\b\d{4}\b',             # Années ou numéros 4 chiffres
        ]
    
    def _get_search_zones(self, rect_x, rect_y, rect_w, rect_h, img_w, img_h, all_rectangles, current_idx):
        """
        Définit les zones de recherche autour d'un rectangle en évitant les chevauchements
        """
        margin = 80  # Marge de recherche autour du rectangle (augmentée)
        zone_height = 120  # Hauteur des zones de recherche (augmentée)
        zone_width = 160   # Largeur des zones de recherche (augmentée)
        
        # Zones potentielles
        zones = {}
        
        # Zone BAS (sous le rectangle)
        bottom_y = rect_y + rect_h + 10
        if bottom_y + zone_height < img_h:
            zones['bottom'] = {
                'x': max(0, rect_x - margin),
                'y': bottom_y,
                'w': min(rect_w + 2*margin, img_w - max(0, rect_x - margin)),
                'h': min(zone_height, img_h - bottom_y)
            }
        
        # Zone DROITE (à droite du rectangle)
        right_x = rect_x + rect_w + 10
        if right_x + zone_width < img_w:
            zones['right'] = {
                'x': right_x,
                'y': max(0, rect_y - margin),
                'w': min(zone_width, img_w - right_x),
                'h': min(rect_h + 2*margin, img_h - max(0, rect_y - margin))
            }
        
        # Zone GAUCHE (à gauche du rectangle)
        left_x = rect_x - zone_width - 10
        if left_x > 0:
            zones['left'] = {
                'x': max(0, left_x),
                'y': max(0, rect_y - margin),
                'w': min(zone_width, rect_x - max(0, left_x)),
                'h': min(rect_h + 2*margin, img_h - max(0, rect_y - margin))
            }
        
        # Éliminer les zones qui chevauchent avec d'autres rectangles
        clean_zones = {}
        for zone_name, zone in zones.items():
            if not self._zone_overlaps_with_rectangles(zone, all_rectangles, current_idx):
                clean_zones[zone_name] = zone
        
        return clean_zones
    
    def _zone_overlaps_with_rectangles(self, zone, all_rectangles, current_idx):
        """
        Vérifie si une zone chevauche avec d'autres rectangles
        """
        zone_x1 = zone['x']
        zone_y1 = zone['y'] 
        zone_x2 = zone_x1 + zone['w']
        zone_y2 = zone_y1 + zone['h']
        
        for i, rect in enumerate(all_rectangles):
            if i == current_idx:  # Skip le rectangle actuel
                continue
                
            if 'bbox' in rect:
                bbox = rect['bbox']
                rect_x1 = bbox['x']
                rect_y1 = bbox['y']
                rect_x2 = rect_x1 + bbox['w']
                rect_y2 = rect_y1 + bbox['h']
                
                # Test de chevauchement
                if not (zone_x2 < rect_x1 or zone_x1 > rect_x2 or 
                       zone_y2 < rect_y1 or zone_y1 > rect_y2):
                    return True
        
        return False
    
    def _ocr_search_in_zone(self, image, zone, zone_name):
        """
        Effectue l'OCR dans une zone spécifique
        """
        try:
            # Vérifier si Tesseract est disponible
            if not self._is_tesseract_available():
                logger.warning("⚠️ Tesseract OCR non disponible - numéros désactivés")
                return []
            
            # Extraire la zone
            x, y, w, h = zone['x'], zone['y'], zone['w'], zone['h']
            zone_image = image[y:y+h, x:x+w]
            
            # Prétraitement pour améliorer l'OCR
            zone_processed = self._preprocess_for_ocr(zone_image)
            
            # OCR avec pytesseract - mode optimisé pour numéros
            text = pytesseract.image_to_string(zone_processed, config='--psm 7 -c tessedit_char_whitelist=0123456789 ')
            
            # Chercher des numéros dans le texte
            numbers = self._extract_numbers_from_text(text, zone_name)
            
            logger.info(f"    Zone {zone_name}: texte='{text.strip()}' → numéros={numbers}")
            return numbers
            
        except Exception as e:
            logger.error(f"❌ Erreur OCR zone {zone_name}: {str(e)}")
            return []
    
    def _is_tesseract_available(self):
        """
        Vérifie si Tesseract OCR est disponible via pytesseract
        """
        try:
            # Créer une petite image de test
            import numpy as np
            test_image = np.ones((50, 200, 3), dtype=np.uint8) * 255
            
            # Tester pytesseract directement
            text = pytesseract.image_to_string(test_image, timeout=5)
            return True
        except Exception as e:
            logger.debug(f"Test Tesseract échoué: {e}")
            return False
    
    def detect_artwork_numbers(self, image, rectangles):
        """
        Détecte les numéros d'œuvre pour chaque rectangle
        """
        try:
            logger.info(f"🔍 Détection des numéros d'œuvre pour {len(rectangles)} rectangles")
            
            # Vérifier dès le début si Tesseract est disponible
            if not self._is_tesseract_available():
                logger.warning("⚠️ Tesseract OCR non installé - numéros d'œuvre désactivés")
                logger.info("💡 Pour activer l'OCR, installez Tesseract OCR depuis: https://github.com/UB-Mannheim/tesseract/wiki")
                # Retourner les rectangles sans numéros
                for rectangle in rectangles:
                    rectangle['artwork_number'] = None
                return rectangles
            
            # Copie de l'image pour le traitement OCR
            image_height, image_width = image.shape[:2]
            
            for i, rectangle in enumerate(rectangles):
                logger.info(f"📝 Analyse OCR rectangle {i+1}")
                
                # Récupérer les coordonnées du rectangle
                if 'bbox' in rectangle:
                    bbox = rectangle['bbox']
                    rect_x, rect_y = bbox['x'], bbox['y']
                    rect_w, rect_h = bbox['w'], bbox['h']
                    
                    # Définir les zones à analyser autour du rectangle
                    search_zones = self._get_search_zones(
                        rect_x, rect_y, rect_w, rect_h, 
                        image_width, image_height, rectangles, i
                    )
                    
                    # Chercher des numéros dans chaque zone
                    found_numbers = []
                    for zone_name, zone_coords in search_zones.items():
                        numbers = self._ocr_search_in_zone(image, zone_coords, zone_name)
                        found_numbers.extend(numbers)
                    
                    # Choisir le meilleur numéro trouvé
                    best_number = self._select_best_number(found_numbers)
                    rectangle['artwork_number'] = best_number
                    
                    logger.info(f"  ✅ Rectangle {i+1}: numéro = {best_number}")
                else:
                    rectangle['artwork_number'] = None
                    logger.info(f"  ❌ Rectangle {i+1}: pas de bbox")
            
            return rectangles
            
        except Exception as e:
            logger.error(f"❌ Erreur détection numéros: {str(e)}")
            # En cas d'erreur, retourner les rectangles sans numéros
            for rectangle in rectangles:
                rectangle['artwork_number'] = None
            return rectangles
    
    def _preprocess_for_ocr(self, image):
        """
        Prétraite l'image pour améliorer la reconnaissance OCR des numéros
        """
        # Convertir en niveaux de gris
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Débruitage léger
        denoised = cv2.fastNlMeansDenoising(gray, h=3)
        
        # Améliorer le contraste de façon plus douce
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
        enhanced = clahe.apply(denoised)
        
        # Binarisation simple avec seuil d'Otsu
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Agrandir davantage pour améliorer l'OCR
        scale_factor = 4
        height, width = binary.shape
        enlarged = cv2.resize(binary, (width * scale_factor, height * scale_factor), 
                            interpolation=cv2.INTER_CUBIC)
        
        # Morphologie pour nettoyer
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(enlarged, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _extract_numbers_from_text(self, text, zone_name):
        """
        Extrait les numéros d'un texte OCR en utilisant des regex
        """
        numbers = []
        text_clean = text.strip()
        
        if not text_clean:
            return numbers
        
        for pattern in self.number_patterns:
            matches = re.findall(pattern, text_clean, re.IGNORECASE)
            for match in matches:
                # Validation du numéro trouvé
                if self._is_valid_artwork_number(match):
                    numbers.append({
                        'number': match,
                        'zone': zone_name,
                        'pattern': pattern,
                        'confidence': self._calculate_confidence(match, zone_name)
                    })
        
        return numbers
    
    def _is_valid_artwork_number(self, number_str):
        """
        Valide si un numéro trouvé peut être un numéro d'œuvre
        """
        # Supprimer les espaces et caractères spéciaux
        clean_number = re.sub(r'[^\w]', '', number_str)
        
        # Doit contenir au moins un chiffre
        if not re.search(r'\d', clean_number):
            return False
        
        # Longueur raisonnable
        if len(clean_number) < 1 or len(clean_number) > 8:
            return False
        
        # Éviter les dates complètes (ex: 20231205)
        if len(clean_number) == 8 and clean_number.isdigit():
            return False
        
        return True
    
    def _calculate_confidence(self, number, zone_name):
        """
        Calcule un score de confiance pour un numéro trouvé
        """
        confidence = 0.5  # Base
        
        # Bonus selon la zone (bottom est prioritaire)
        zone_bonus = {
            'bottom': 0.3,
            'right': 0.2, 
            'left': 0.1
        }
        confidence += zone_bonus.get(zone_name, 0)
        
        # Bonus selon le format
        if re.match(r'^\d{1,4}$', number):  # Numéro simple
            confidence += 0.2
        elif re.match(r'^\d{1,3}[-\.]\d{1,4}$', number):  # Format XX-XXXX
            confidence += 0.3
        elif 'N°' in number or 'No' in number:  # Format N° explicite
            confidence += 0.4
        
        return min(1.0, confidence)
    
    def _select_best_number(self, found_numbers):
        """
        Sélectionne le meilleur numéro parmi ceux trouvés
        """
        if not found_numbers:
            return None
        
        # Trier par confiance décroissante
        sorted_numbers = sorted(found_numbers, key=lambda x: x['confidence'], reverse=True)
        
        best = sorted_numbers[0]
        logger.info(f"    Meilleur: {best['number']} (zone: {best['zone']}, confiance: {best['confidence']:.2f})")
        
        return best['number']

# Initialiser les détecteurs
detector = RectangleDetector()
artwork_detector = ArtworkNumberDetector()

@app.route('/upload', methods=['POST'])
def upload_file():
    """Endpoint pour uploader et analyser une image ou PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400
        
        if file and allowed_file(file.filename):
            # Sauvegarder le fichier
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Obtenir les paramètres
            sensitivity = int(request.form.get('sensitivity', 50))
            mode = request.form.get('mode', 'general')
            
            # Adapter les paramètres selon le mode
            if mode == 'documents':
                logger.info("Mode documents multiples activé")
                sensitivity = max(70, sensitivity)
            elif mode == 'high_contrast':
                logger.info("Mode objets contrastés activé")
                sensitivity = min(40, sensitivity)
            else:
                logger.info("Mode général activé")
            
            # **NOUVEAU : Traitement PDF ou Image**
            if is_pdf(filename):
                # Récupérer le paramètre pour ignorer la vérification OCR
                skip_ocr = request.form.get('skip_ocr_detection', 'false').lower() == 'true'
                
                # **NOUVEAU: Faire l'analyse OCR EN PREMIER, AVANT le thread**
                logger.info("🔍 Pré-analyse OCR avant traitement...")
                
                if not skip_ocr:
                    # Analyse OCR rapide pour décider
                    ocr_info = ocr_detector.has_existing_ocr(filepath)
                    
                    # Émettre les résultats de l'analyse OCR
                    socketio.emit('ocr_analysis', ocr_info)
                    logger.info(f"📋 Résultats OCR: {ocr_info['recommendation']}")
                    
                    # **ARRÊTER ICI SI OCR DÉTECTÉ**
                    if ocr_info['has_ocr']:
                        logger.info("⏸️ OCR détecté - PAUSE pour choix utilisateur")
                        return jsonify({
                            'success': True,
                            'ocr_decision_required': True,
                            'message': 'Analyse OCR terminée - Choix utilisateur requis',
                            'filename': filename,
                            'is_pdf': True,
                            'ocr_info': ocr_info
                        })
                    else:
                        logger.info("🚀 Aucun OCR - Continuation automatique...")
                
                # Variables globales pour stocker les résultats du traitement asynchrone
                pdf_processor.current_result = None
                pdf_processor.processing_in_progress = True
                
                # Traitement PDF multi-pages avec progression temps réel
                def process_async():
                    try:
                        # MAINTENANT skip_ocr = True car on a déjà testé
                        result = pdf_processor.process_pdf(filepath, detector, sensitivity, mode, skip_ocr_detection=True)
                        pdf_processor.current_result = result
                        pdf_processor.processing_in_progress = False
                        
                        # Émettre un événement final avec les résultats
                        if result['success']:
                            socketio.emit('results_ready', {
                                'success': True,
                                'data': result
                            })
                        else:
                            socketio.emit('results_ready', {
                                'success': False,
                                'error': result.get('error', 'Erreur inconnue')
                            })
                        
                        return result
                    except Exception as e:
                        logger.error(f"Erreur traitement async: {e}")
                        error_result = {'success': False, 'error': str(e)}
                        pdf_processor.current_result = error_result
                        pdf_processor.processing_in_progress = False
                        
                        socketio.emit('results_ready', {
                            'success': False,
                            'error': str(e)
                        })
                        
                        return error_result
                
                # Démarrer le traitement dans un thread pour permettre les mises à jour temps réel
                import threading
                processing_thread = threading.Thread(target=process_async)
                processing_thread.start()
                
                # Retourner immédiatement une réponse indiquant que le traitement a commencé
                return jsonify({
                    'success': True,
                    'message': 'Traitement PDF démarré',
                    'filename': filename,
                    'is_pdf': True,
                    'processing_started': True,
                    'websocket_enabled': True
                })
                
            else:
                # Traitement image classique
                image = cv2.imread(filepath)
                if image is None:
                    return jsonify({'error': 'Impossible de lire l\'image'}), 400
                
                # Détecter les rectangles (bbox déjà converti en dict)
                rectangles = detector.detect_rectangles(image, sensitivity, mode)
                
                # Préparer la réponse
                result = {
                    'filename': filename,
                    'rectangles_count': len(rectangles),
                    'rectangles': []
                }
                
                # Ajouter les informations des rectangles
                for rect in rectangles:
                    bbox = rect['bbox']  # Maintenant c'est déjà un dict
                    result['rectangles'].append({
                        'id': rect['id'],
                        'bbox': bbox,  # Déjà au bon format
                        'area': int(rect['area']),
                        'corners': rect['corners'].tolist(),
                        'is_bounding_box': rect.get('is_bounding_box', False),
                        'confidence': rect.get('confidence'),
                        'mode': rect.get('mode'),
                        'artwork_number': rect.get('artwork_number')  # Ajouter le numéro d'œuvre
                    })
                
                # Stocker les rectangles en session
                detector.rectangles = rectangles
                detector.current_image = image
                detector.current_filename = filename
                
                logger.info(f"Image {filename} analysée: {len(rectangles)} rectangles détectés")
                return jsonify(result)
        
        return jsonify({'error': 'Format de fichier non supporté'}), 400
        
    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/extract/<int:rectangle_id>')
def extract_rectangle_endpoint(rectangle_id):
    """Endpoint pour extraire un rectangle spécifique"""
    try:
        if not hasattr(detector, 'rectangles') or not detector.rectangles:
            return jsonify({'error': 'Aucune image analysée'}), 400
        
        if rectangle_id >= len(detector.rectangles):
            return jsonify({'error': 'Rectangle non trouvé'}), 404
        
        # Paramètres
        format_type = request.args.get('format', 'png')
        
        rectangle = detector.rectangles[rectangle_id]
        
        # Extraire et redresser le rectangle
        extracted = detector.extract_rectangle(detector.current_image, rectangle)
        
        # Convertir BGR vers RGB
        extracted_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(extracted_rgb, 'RGB')
        
        # Sauvegarder en mémoire
        img_buffer = io.BytesIO()
        if format_type.lower() == 'png':
            pil_image.save(img_buffer, format='PNG')
            mimetype = 'image/png'
        else:
            pil_image.save(img_buffer, format='JPEG', quality=95)
            mimetype = 'image/jpeg'
        
        img_buffer.seek(0)
        
        filename = f"rectangle-{rectangle_id + 1}-extrait.{format_type.lower()}"
        
        return send_file(
            img_buffer, 
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/preview/<int:rectangle_id>')
def preview_rectangle(rectangle_id):
    """Endpoint pour prévisualiser un rectangle avec ses coins"""
    try:
        if not hasattr(detector, 'rectangles') or not detector.rectangles:
            return jsonify({'error': 'Aucune image analysée'}), 400
        
        if rectangle_id >= len(detector.rectangles):
            return jsonify({'error': 'Rectangle non trouvé'}), 404
        
        rectangle = detector.rectangles[rectangle_id]
        
        # Créer une prévisualisation avec les coins marqués
        preview = detector.create_preview_with_corners(detector.current_image, rectangle)
        
        # Redimensionner pour la prévisualisation
        preview_size = 400
        height, width = preview.shape[:2]
        
        if width > height:
            new_width = preview_size
            new_height = int(height * preview_size / width)
        else:
            new_height = preview_size
            new_width = int(width * preview_size / height)
        
        preview_resized = cv2.resize(preview, (new_width, new_height))
        
        # Convertir en format web
        preview_rgb = cv2.cvtColor(preview_resized, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(preview_rgb, 'RGB')
        
        img_buffer = io.BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Erreur lors de la prévisualisation: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/extract_all')
def extract_all_rectangles():
    """Endpoint pour télécharger tous les rectangles dans un ZIP"""
    try:
        if not hasattr(detector, 'rectangles') or not detector.rectangles:
            return jsonify({'error': 'Aucune image analysée'}), 400
        
        import zipfile
        from io import BytesIO
        
        # Créer un buffer pour le ZIP
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, rectangle in enumerate(detector.rectangles):
                # Extraire le rectangle
                extracted = detector.extract_rectangle(detector.current_image, rectangle)
                extracted_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(extracted_rgb, 'RGB')
                
                # PNG haute qualité
                png_buffer = BytesIO()
                pil_image.save(png_buffer, format='PNG')
                zip_file.writestr(f'rectangle-{i+1}-extrait.png', png_buffer.getvalue())
                
                # JPG haute qualité
                jpg_buffer = BytesIO()
                pil_image.save(jpg_buffer, format='JPEG', quality=95)
                zip_file.writestr(f'rectangle-{i+1}-extrait.jpg', jpg_buffer.getvalue())
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'tous-rectangles-extraits-{len(detector.rectangles)}.zip'
        )
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement en lot: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/pdf_preview/<int:page_number>/<int:rectangle_id>')
def preview_pdf_rectangle(page_number, rectangle_id):
    """Endpoint pour prévisualiser un rectangle d'une page PDF"""
    try:
        logger.info(f"🔍 PREVIEW PDF: page {page_number}, rectangle {rectangle_id}")
        
        if not pdf_processor.pages or not pdf_processor.pdf_rectangles:
            logger.error("❌ Aucune donnée PDF disponible pour preview")
            return jsonify({'error': 'Aucun PDF analysé'}), 400
        
        # Trouver la page et le rectangle (même logique que extract)
        logger.info(f"Recherche page {page_number} pour preview")
        page_data = None
        for page in pdf_processor.pages:
            if page['page_number'] == page_number:
                page_data = page
                logger.info(f"✅ Page {page_number} trouvée pour preview")
                break
                
        if not page_data:
            logger.error(f"❌ Page {page_number} non trouvée pour preview")
            return jsonify({'error': 'Page non trouvée'}), 404
            
        # Trouver le rectangle sur cette page
        page_rectangles = None
        for page_result in pdf_processor.pdf_rectangles:
            if page_result['page_number'] == page_number:
                page_rectangles = page_result['rectangles']
                logger.info(f"✅ Page {page_number} a {len(page_rectangles)} rectangles pour preview")
                break
                
        if not page_rectangles or rectangle_id >= len(page_rectangles):
            logger.error(f"❌ Rectangle {rectangle_id} non trouvé pour preview")
            return jsonify({'error': 'Rectangle non trouvé'}), 404
            
        rectangle = page_rectangles[rectangle_id]
        logger.info(f"✅ Rectangle {rectangle_id} trouvé pour preview")
        
        # **RECONSTRUIRE LES CORNERS EN ARRAY NUMPY**
        if 'corners' in rectangle and isinstance(rectangle['corners'], list):
            rectangle['corners'] = np.array(rectangle['corners'], dtype=np.float32)
            logger.info("✅ Corners convertis pour preview")
        
        # Créer une prévisualisation avec les coins marqués
        logger.info("🚀 Création preview avec coins...")
        preview = detector.create_preview_with_corners(page_data['image'], rectangle)
        logger.info("✅ Preview créé")
        
        # Redimensionner pour la prévisualisation
        preview_size = 400
        height, width = preview.shape[:2]
        
        if width > height:
            new_width = preview_size
            new_height = int(height * preview_size / width)
        else:
            new_height = preview_size
            new_width = int(width * preview_size / height)
        
        preview_resized = cv2.resize(preview, (new_width, new_height))
        
        # Convertir en format web
        preview_rgb = cv2.cvtColor(preview_resized, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(preview_rgb, 'RGB')
        
        img_buffer = io.BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        logger.info(f"🎉 SUCCÈS PREVIEW: page {page_number}, rectangle {rectangle_id}")
        return send_file(img_buffer, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"💥 ERREUR PREVIEW PDF: {str(e)}")
        import traceback
        logger.error(f"💥 Traceback preview: {traceback.format_exc()}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/pdf_extract/<int:page_number>/<int:rectangle_id>')
def extract_pdf_rectangle(page_number, rectangle_id):
    """Endpoint pour extraire un rectangle d'une page PDF"""
    try:
        logger.info(f"🔍 EXTRACTION PDF: page {page_number}, rectangle {rectangle_id}")
        
        if not pdf_processor.pages or not pdf_processor.pdf_rectangles:
            logger.error("❌ Aucune donnée PDF disponible")
            return jsonify({'error': 'Aucun PDF analysé'}), 400
        
        format_type = request.args.get('format', 'png')
        logger.info(f"Format demandé: {format_type}")
        
        # Trouver la page et le rectangle
        logger.info(f"Recherche page {page_number} dans {len(pdf_processor.pages)} pages disponibles")
        page_data = None
        for page in pdf_processor.pages:
            if page['page_number'] == page_number:
                page_data = page
                logger.info(f"✅ Page {page_number} trouvée")
                break
                
        if not page_data:
            logger.error(f"❌ Page {page_number} non trouvée")
            return jsonify({'error': 'Page non trouvée'}), 404
            
        logger.info(f"Recherche rectangles pour page {page_number}")
        page_rectangles = None
        for page_result in pdf_processor.pdf_rectangles:
            if page_result['page_number'] == page_number:
                page_rectangles = page_result['rectangles']
                logger.info(f"✅ Page {page_number} a {len(page_rectangles)} rectangles")
                break
                
        if not page_rectangles:
            logger.error(f"❌ Aucun rectangle trouvé pour page {page_number}")
            return jsonify({'error': 'Aucun rectangle sur cette page'}), 404
            
        if rectangle_id >= len(page_rectangles):
            logger.error(f"❌ Rectangle {rectangle_id} non trouvé (max: {len(page_rectangles)-1})")
            return jsonify({'error': 'Rectangle non trouvé'}), 404
            
        rectangle = page_rectangles[rectangle_id]
        logger.info(f"✅ Rectangle {rectangle_id} trouvé")
        logger.info(f"Rectangle data: {rectangle}")
        
        # **RECONSTRUIRE LES CORNERS EN ARRAY NUMPY**
        if 'corners' in rectangle:
            logger.info(f"Corners type: {type(rectangle['corners'])}, value: {rectangle['corners']}")
            if isinstance(rectangle['corners'], list):
                rectangle['corners'] = np.array(rectangle['corners'], dtype=np.float32)
                logger.info("✅ Corners convertis de liste vers array NumPy")
        
        # Extraire et redresser le rectangle
        logger.info("🚀 Début extraction rectangle...")
        extracted = detector.extract_rectangle(page_data['image'], rectangle)
        logger.info(f"✅ Rectangle extrait: {extracted.shape}")
        
        # Convertir BGR vers RGB
        extracted_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(extracted_rgb, 'RGB')
        logger.info("✅ Conversion en PIL Image réussie")
        
        # Sauvegarder en mémoire
        img_buffer = io.BytesIO()
        if format_type.lower() == 'png':
            pil_image.save(img_buffer, format='PNG')
            mimetype = 'image/png'
        else:
            pil_image.save(img_buffer, format='JPEG', quality=95)
            mimetype = 'image/jpeg'
        
        img_buffer.seek(0)
        logger.info("✅ Image sauvegardée en mémoire")
        
        filename = f"page-{page_number}-rectangle-{rectangle_id + 1}.{format_type.lower()}"
        
        logger.info(f"🎉 SUCCÈS: Envoi de {filename}")
        return send_file(
            img_buffer, 
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"💥 ERREUR EXTRACTION PDF: {str(e)}")
        logger.error(f"💥 Type erreur: {type(e)}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/pdf_extract_all')
def extract_all_pdf_rectangles():
    """Endpoint pour télécharger tous les rectangles de toutes les pages PDF en ZIP"""
    try:
        logger.info("🗂️ EXTRACTION PDF COMPLÈTE")
        
        if not pdf_processor.pages or not pdf_processor.pdf_rectangles:
            logger.error("❌ Aucune donnée PDF disponible")
            return jsonify({'error': 'Aucun PDF analysé'}), 400
        
        if not pdf_processor.original_filename:
            logger.error("❌ Nom du fichier PDF manquant")
            return jsonify({'error': 'Nom du fichier PDF non disponible'}), 400
        
        # Créer un ZIP en mémoire
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            total_extracted = 0
            
            for page_result in pdf_processor.pdf_rectangles:
                page_number = page_result['page_number']
                rectangles = page_result['rectangles']
                
                logger.info(f"📄 Traitement page {page_number} ({len(rectangles)} rectangles)")
                
                # Trouver l'image de cette page
                page_data = None
                for page in pdf_processor.pages:
                    if page['page_number'] == page_number:
                        page_data = page
                        break
                
                if not page_data:
                    logger.warning(f"⚠️ Image de la page {page_number} non trouvée")
                    continue
                
                # Extraire chaque rectangle de cette page
                for rect_idx, rectangle in enumerate(rectangles):
                    try:
                        # **RECONSTRUIRE LES CORNERS EN ARRAY NUMPY** (même fix qu'avant)
                        if 'corners' in rectangle and isinstance(rectangle['corners'], list):
                            rectangle['corners'] = np.array(rectangle['corners'], dtype=np.float32)
                        
                        # Extraire le rectangle
                        extracted = detector.extract_rectangle(page_data['image'], rectangle)
                        
                        # Convertir en RGB pour PIL
                        extracted_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(extracted_rgb, 'RGB')
                        
                        # **NOUVEAU NAMING INTELLIGENT AVEC NUMÉROS D'ŒUVRE**
                        base_filename = pdf_processor.original_filename
                        
                        # Essayer d'utiliser le numéro d'œuvre si disponible
                        if 'artwork_number' in rectangle and rectangle['artwork_number']:
                            # Format: nomfichier_numerooeuvre_page-XX.png
                            filename = f"{base_filename}_{rectangle['artwork_number']}_page-{page_number:02d}.png"
                        else:
                            # Format fallback: nomfichier_page-XX_rectangle-XX.png
                            filename = f"{base_filename}_page-{page_number:02d}_rectangle-{rect_idx + 1:02d}.png"
                        
                        logger.info(f"📁 Nom de fichier: {filename}")
                        
                        # Sauvegarder l'image en mémoire
                        img_buffer = io.BytesIO()
                        pil_image.save(img_buffer, format='PNG')
                        
                        # Ajouter au ZIP (directement à la racine, pas de sous-dossiers)
                        zip_file.writestr(filename, img_buffer.getvalue())
                        
                        total_extracted += 1
                        logger.info(f"✅ Ajouté: {filename}")
                        
                    except Exception as e:
                        logger.error(f"❌ Erreur extraction rectangle {rect_idx} page {page_number}: {str(e)}")
                        continue
        
        zip_buffer.seek(0)
        
        # **NOUVEAU NOM DE ZIP INTELLIGENT**
        # Format: nomfichier.zip (au lieu de pdf-complet-X-rectangles.zip)
        zip_filename = f"{pdf_processor.original_filename}.zip"
        
        logger.info(f"🎉 ZIP créé: {zip_filename} avec {total_extracted} rectangles")
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        logger.error(f"💥 ERREUR CRÉATION ZIP PDF: {str(e)}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/extract_ocr/<filename>')
def extract_ocr_from_pdf(filename):
    """Endpoint pour extraire directement le texte OCR d'un PDF"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        if not is_pdf(filename):
            return jsonify({'error': 'Fichier doit être un PDF'}), 400
        
        logger.info(f"📄 Extraction OCR directe de {filename}")
        
        # Extraire tout le texte du PDF
        full_text = ""
        page_texts = []
        
        # Méthode 1: PyPDF2
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num in range(min(5, total_pages)):  # Limiter à 5 pages pour demo
                    try:
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text().strip()
                        if text:
                            page_texts.append(f"=== PAGE {page_num + 1} ===\n{text}\n")
                            full_text += text + "\n\n"
                    except Exception as e:
                        logger.warning(f"Erreur page {page_num + 1}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Erreur extraction PyPDF2: {e}")
            return jsonify({'error': 'Impossible d\'extraire le texte OCR'}), 500
        
        if not full_text.strip():
            return jsonify({'error': 'Aucun texte OCR trouvé'}), 400
        
        logger.info(f"✅ OCR extrait: {len(full_text)} caractères")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_pages': total_pages,
            'extracted_text': full_text[:2000] + "..." if len(full_text) > 2000 else full_text,  # Limiter pour demo
            'full_text': full_text,
            'page_texts': page_texts,
            'method': 'direct_ocr_extraction'
        })
        
    except Exception as e:
        logger.error(f"Erreur extraction OCR: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/pdf_results')
def get_pdf_results():
    """Endpoint pour récupérer les résultats du traitement PDF asynchrone"""
    try:
        if not hasattr(pdf_processor, 'current_result') or pdf_processor.current_result is None:
            if hasattr(pdf_processor, 'processing_in_progress') and pdf_processor.processing_in_progress:
                return jsonify({
                    'success': False,
                    'processing': True,
                    'message': 'Traitement en cours...'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Aucun résultat disponible'
                }), 404
        
        result = pdf_processor.current_result
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erreur récupération résultats PDF: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/ocr_check/<filename>')
def check_ocr_in_pdf(filename):
    """Endpoint pour vérifier l'OCR existant dans un PDF"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        if not is_pdf(filename):
            return jsonify({'error': 'Fichier doit être un PDF'}), 400
        
        # Vérifier l'OCR
        ocr_info = ocr_detector.has_existing_ocr(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'ocr_info': ocr_info
        })
        
    except Exception as e:
        logger.error(f"Erreur vérification OCR: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/health')
def health_check():
    """Endpoint de vérification de santé"""
    return jsonify({
        'status': 'OK', 
        'message': 'Backend de détection de rectangles opérationnel',
        'features': {
            'websockets': True,
            'progress_tracking': True,
            'ocr_detection': True
        }
    })

@app.route('/continue_with_ai/<filename>')
def continue_with_ai_processing(filename):
    """Endpoint pour continuer avec le traitement IA après analyse OCR"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🚀 Continuation traitement IA pour {filename}")
        
        # Récupérer les paramètres de la session
        sensitivity = int(request.args.get('sensitivity', 50))
        mode = request.args.get('mode', 'general')
        
        # Variables globales pour stocker les résultats du traitement asynchrone
        pdf_processor.current_result = None
        pdf_processor.processing_in_progress = True
        
        # Traitement PDF avec progression temps réel (skip OCR)
        def process_async():
            try:
                result = pdf_processor.process_pdf(filepath, detector, sensitivity, mode, skip_ocr_detection=True)
                pdf_processor.current_result = result
                pdf_processor.processing_in_progress = False
                
                # Émettre un événement final avec les résultats
                if result['success']:
                    socketio.emit('results_ready', {
                        'success': True,
                        'data': result
                    })
                else:
                    socketio.emit('results_ready', {
                        'success': False,
                        'error': result.get('error', 'Erreur inconnue')
                    })
                
                return result
            except Exception as e:
                logger.error(f"Erreur traitement async: {e}")
                error_result = {'success': False, 'error': str(e)}
                pdf_processor.current_result = error_result
                pdf_processor.processing_in_progress = False
                
                socketio.emit('results_ready', {
                    'success': False,
                    'error': str(e)
                })
                
                return error_result
        
        # Démarrer le traitement dans un thread
        import threading
        processing_thread = threading.Thread(target=process_async)
        processing_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Traitement IA démarré',
            'filename': filename,
            'processing_started': True
        })
        
    except Exception as e:
        logger.error(f"Erreur continuation IA: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/extract_images/<filename>')
def extract_images_from_pdf(filename):
    """Endpoint pour extraire directement les images du PDF"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🖼️ Extraction directe des images de {filename}")
        
        import fitz  # PyMuPDF
        import zipfile
        import io
        
        # Ouvrir le PDF
        doc = fitz.open(filepath)
        images_found = []
        
        # Créer un ZIP en mémoire pour toutes les images
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            image_count = 0
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                logger.info(f"📄 Page {page_num + 1}: {len(image_list)} images trouvées")
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Extraire l'image
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        # Convertir en format standard si nécessaire
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                            image_count += 1
                            
                            # Nom de fichier intelligent
                            img_filename = f"page-{page_num+1:03d}_image-{img_index+1:02d}.png"
                            
                            # Ajouter au ZIP
                            zip_file.writestr(img_filename, img_data)
                            
                            # Info pour la réponse
                            images_found.append({
                                'page': page_num + 1,
                                'image_index': img_index + 1,
                                'filename': img_filename,
                                'width': pix.width,
                                'height': pix.height,
                                'size_kb': len(img_data) // 1024
                            })
                            
                            logger.info(f"  ✅ {img_filename}: {pix.width}x{pix.height} ({len(img_data)//1024} KB)")
                            
                        else:  # CMYK, etc.
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            img_data = pix1.tobytes("png")
                            image_count += 1
                            
                            img_filename = f"page-{page_num+1:03d}_image-{img_index+1:02d}.png"
                            zip_file.writestr(img_filename, img_data)
                            
                            images_found.append({
                                'page': page_num + 1,
                                'image_index': img_index + 1,
                                'filename': img_filename,
                                'width': pix1.width,
                                'height': pix1.height,
                                'size_kb': len(img_data) // 1024
                            })
                            
                            pix1 = None
                            
                        pix = None
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur extraction image page {page_num+1}, index {img_index}: {e}")
                        continue
        
        doc.close()
        
        if image_count == 0:
            return jsonify({'error': 'Aucune image trouvée dans le PDF'}), 400
        
        logger.info(f"✅ Extraction terminée: {image_count} images trouvées")
        
        # Préparer le ZIP pour téléchargement
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{filename.replace(".pdf", "")}_images_extraites.zip'
        )
        
    except Exception as e:
        logger.error(f"Erreur extraction images: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Connexion WebSocket établie"""
    logger.info("🔗 Client WebSocket connecté")
    emit('connected', {'message': 'Connexion WebSocket établie'})

@socketio.on('disconnect')
def handle_disconnect():
    """Déconnexion WebSocket"""
    logger.info("❌ Client WebSocket déconnecté")

if __name__ == '__main__':
    print("🚀 Démarrage du backend de détection de rectangles")
    print("📡 API disponible sur http://localhost:5000")
    print("🔗 WebSockets activés pour progression temps réel")
    print("📋 Endpoints:")
    print("   POST /upload - Upload et analyse d'image/PDF")
    print("   GET  /ocr_check/<filename> - Vérifier OCR existant")
    print("   GET  /extract/<id> - Télécharger rectangle extrait")
    print("   GET  /preview/<id> - Prévisualiser rectangle avec coins")
    print("   GET  /health - Status du serveur")
    print("🆕 Nouvelles fonctionnalités:")
    print("   ⏱️  Progression en temps réel pour PDF volumineux")
    print("   🤖 Détection automatique OCR existant")
    print("   📊 Estimation du temps restant")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 