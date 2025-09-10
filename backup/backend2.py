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
import shutil
import json
from pathlib import Path
from datetime import datetime
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

class RealtimeSaver:
    """
    Sauvegarde automatique des images détectées en temps réel
    dans un dossier organisé avec aperçu pendant le traitement
    """
    
    def __init__(self):
        self.output_base_dir = "extractions"
        self.current_session_dir = None
        self.saved_count = 0
        self.saved_files = []
        
    def create_session_folder(self, pdf_name):
        """Crée un dossier unique pour cette session d'extraction"""
        # Nettoyer le nom du PDF
        clean_name = os.path.splitext(pdf_name)[0]
        clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip()
        
        # Créer un nom unique avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = f"{clean_name}_{timestamp}"
        
        # Créer le dossier
        self.current_session_dir = os.path.join(self.output_base_dir, session_name)
        os.makedirs(self.current_session_dir, exist_ok=True)
        
        # Créer des sous-dossiers
        os.makedirs(os.path.join(self.current_session_dir, "avec_numeros"), exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "sans_numeros"), exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "miniatures"), exist_ok=True)
        
        logger.info(f"📁 Dossier de session créé: {self.current_session_dir}")
        
        # Créer un fichier info
        info_path = os.path.join(self.current_session_dir, "info.txt")
        with open(info_path, 'w', encoding='utf-8') as f:
            f.write(f"Extraction de: {pdf_name}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Mode: Automatique intelligent\n")
            f.write("-" * 50 + "\n")
        
        return self.current_session_dir
    
    def save_rectangle_immediately(self, image, rectangle, page_num, rect_num, artwork_number=None):
        """
        Sauvegarde immédiatement une image extraite
        """
        try:
            if not self.current_session_dir:
                logger.error("❌ Pas de dossier de session")
                return None
            
            # Extraire l'image du rectangle
            extracted = self._extract_rectangle_image(image, rectangle)
            if extracted is None:
                return None
            
            # Déterminer le nom et le dossier
            if artwork_number:
                filename = f"oeuvre_{artwork_number}_p{page_num:03d}.png"
                folder = os.path.join(self.current_session_dir, "avec_numeros")
            else:
                filename = f"page_{page_num:03d}_rect_{rect_num:02d}.png"
                folder = os.path.join(self.current_session_dir, "sans_numeros")
            
            filepath = os.path.join(folder, filename)
            
            # Sauvegarder l'image principale
            cv2.imwrite(filepath, extracted)
            
            # Créer une miniature pour aperçu rapide
            thumbnail = self._create_thumbnail(extracted)
            thumb_path = os.path.join(self.current_session_dir, "miniatures", f"thumb_{filename}")
            cv2.imwrite(thumb_path, thumbnail)
            
            self.saved_count += 1
            self.saved_files.append({
                'filename': filename,
                'path': filepath,
                'page': page_num,
                'rectangle': rect_num,
                'artwork_number': artwork_number,
                'size': os.path.getsize(filepath)
            })
            
            logger.info(f"💾 Sauvegardé: {filename} ({self.saved_count} total)")
            
            # Mettre à jour le fichier info
            self._update_info_file(filename, page_num, artwork_number)
            
            # Émettre un événement pour le frontend
            socketio.emit('image_saved', {
                'filename': filename,
                'page': page_num,
                'artwork_number': artwork_number,
                'total_saved': self.saved_count,
                'thumbnail_path': thumb_path,
                'file_size': os.path.getsize(filepath) // 1024  # en KB
            })
            
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
            return None
    
    def _extract_rectangle_image(self, image, rectangle):
        """Extrait et redresse l'image du rectangle"""
        try:
            # Reconstruire les corners si nécessaire
            if 'corners' in rectangle:
                corners = rectangle['corners']
                if isinstance(corners, list):
                    corners = np.array(corners, dtype=np.float32)
                
                # Appliquer la transformation de perspective
                warped = self._four_point_transform(image, corners)
                
                # Si trop petit, utiliser bbox
                if warped.shape[0] < 50 or warped.shape[1] < 50:
                    bbox = rectangle.get('bbox', {})
                    if isinstance(bbox, dict):
                        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                    else:
                        x, y, w, h = bbox
                    warped = image[y:y+h, x:x+w]
            else:
                # Utiliser directement bbox
                bbox = rectangle.get('bbox', {})
                if isinstance(bbox, dict):
                    x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                else:
                    x, y, w, h = bbox
                warped = image[y:y+h, x:x+w]
            
            return warped
            
        except Exception as e:
            logger.error(f"Erreur extraction: {e}")
            return None
    
    def _four_point_transform(self, image, pts):
        """Transformation de perspective"""
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect
        
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
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
    
    def _create_thumbnail(self, image, max_size=200):
        """Crée une miniature pour aperçu rapide"""
        height, width = image.shape[:2]
        
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        thumbnail = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return thumbnail
    
    def _update_info_file(self, filename, page_num, artwork_number):
        """Met à jour le fichier info avec la dernière image sauvée"""
        try:
            info_path = os.path.join(self.current_session_dir, "info.txt")
            with open(info_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%H:%M:%S')
                if artwork_number:
                    f.write(f"[{timestamp}] Page {page_num}: {filename} (Œuvre n°{artwork_number})\n")
                else:
                    f.write(f"[{timestamp}] Page {page_num}: {filename}\n")
        except Exception as e:
            logger.error(f"Erreur mise à jour info: {e}")
    
    def create_summary(self):
        """Crée un résumé HTML de l'extraction"""
        if not self.current_session_dir:
            return
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Résumé Extraction</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; }}
                .stats {{ background: white; padding: 20px; border-radius: 10px; margin: 20px 0; }}
                .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }}
                .image-card {{ background: white; padding: 10px; border-radius: 5px; text-align: center; }}
                .image-card img {{ max-width: 100%; border-radius: 3px; }}
                .artwork-number {{ background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px; margin: 5px 0; display: inline-block; }}
            </style>
        </head>
        <body>
            <h1>📊 Résumé de l'extraction</h1>
            <div class="stats">
                <p>📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>🖼️ Total images extraites: {self.saved_count}</p>
                <p>🎨 Avec numéros d'œuvre: {sum(1 for f in self.saved_files if f['artwork_number'])}</p>
                <p>📄 Sans numéros: {sum(1 for f in self.saved_files if not f['artwork_number'])}</p>
                <p>💾 Taille totale: {sum(f['size'] for f in self.saved_files) / (1024*1024):.2f} MB</p>
            </div>
            <h2>Galerie des miniatures</h2>
            <div class="gallery">
        """
        
        for file_info in self.saved_files:
            thumb_name = f"thumb_{file_info['filename']}"
            html_content += f"""
                <div class="image-card">
                    <img src="miniatures/{thumb_name}" alt="{file_info['filename']}">
                    <p>{file_info['filename']}</p>
                    {'<span class="artwork-number">N°' + str(file_info['artwork_number']) + '</span>' if file_info['artwork_number'] else ''}
                    <p style="font-size: 11px; color: #999;">Page {file_info['page']} • {file_info['size']//1024} KB</p>
                </div>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        summary_path = os.path.join(self.current_session_dir, "resume.html")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"📊 Résumé HTML créé: {summary_path}")
        return summary_path

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

    def process_pdf_auto(self, pdf_path):
        """
        Version automatique du traitement PDF qui s'adapte à chaque page
        """
        try:
            logger.info(f"🤖 TRAITEMENT AUTOMATIQUE INTELLIGENT - {pdf_path}")
            
            # Initialiser le détecteur automatique
            auto_detector = SmartAutoDetector()
            
            # Compter les pages
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
            
            logger.info(f"📄 PDF: {total_pages} pages à traiter automatiquement")
            
            self.pages = []
            self.pdf_rectangles = []
            total_rectangles = 0
            
            # Émettre le début
            socketio.emit('auto_processing_start', {
                'total_pages': total_pages,
                'message': '🤖 Traitement automatique intelligent activé'
            })
            
            for page_num in range(1, min(total_pages + 1, 200)):  # Limiter pour éviter timeout
                try:
                    logger.info(f"📄 Page {page_num}/{total_pages}: Analyse automatique...")
                    
                    # Analyser les dimensions de la page
                    page_analysis = page_analyzer.analyze_page_dimensions(pdf_path, page_num)
                    optimal_dpi = page_analysis['recommended_dpi']
                    
                    # Convertir la page
                    page_images = convert_from_path(
                        pdf_path, 
                        dpi=optimal_dpi,
                        first_page=page_num,
                        last_page=page_num
                    )
                    
                    if not page_images:
                        continue
                    
                    page_image = page_images[0]
                    page_array = np.array(page_image)
                    page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
                    
                    # **DÉTECTION AUTOMATIQUE INTELLIGENTE**
                    rectangles, best_config = auto_detector.auto_detect_best_config(page_cv, page_num)
                    
                    logger.info(f"✅ Page {page_num}: {len(rectangles)} rectangles détectés avec config '{best_config['name']}'")
                    
                    # Convertir pour JSON
                    for rect in rectangles:
                        if 'corners' in rect and hasattr(rect['corners'], 'tolist'):
                            rect['corners'] = rect['corners'].tolist()
                        if 'bbox' in rect and isinstance(rect['bbox'], tuple):
                            x, y, w, h = rect['bbox']
                            rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                        if 'contour' in rect:
                            del rect['contour']
                    
                    # Stocker les résultats
                    page_data = {'page_number': page_num, 'image': page_cv}
                    self.pages.append(page_data)
                    
                    page_result = {
                        'page_number': page_num,
                        'rectangles': rectangles,
                        'rectangles_count': len(rectangles),
                        'auto_config_used': best_config['name']
                    }
                    self.pdf_rectangles.append(page_result)
                    
                    total_rectangles += len(rectangles)
                    
                    # Émettre la progression
                    socketio.emit('auto_page_complete', {
                        'page_number': page_num,
                        'rectangles_found': len(rectangles),
                        'config_used': best_config['name'],
                        'progress_percent': (page_num / total_pages) * 100
                    })
                    
                    # Limiter la mémoire
                    if len(self.pages) > 5:
                        self.pages.pop(0)
                        
                except Exception as e:
                    logger.error(f"❌ Erreur page {page_num}: {e}")
                    continue
            
            logger.info(f"🎉 TRAITEMENT AUTOMATIQUE TERMINÉ: {total_rectangles} rectangles trouvés")
            
            return {
                'success': True,
                'total_pages': len(self.pdf_rectangles),
                'total_rectangles': total_rectangles,
                'pages': self.pdf_rectangles,
                'auto_mode': True
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement automatique: {e}")
            return {'success': False, 'error': str(e)}

    def process_pdf_auto_with_realtime_save(self, pdf_path):
        """MODE AUTOMATIQUE COMPLET - Fait tout automatiquement avec sauvegarde temps réel"""
        try:
            # Initialiser le saver
            saver = RealtimeSaver()
            session_dir = saver.create_session_folder(os.path.basename(pdf_path))
            
            logger.info(f"🤖 MODE AUTOMATIQUE COMPLET ACTIVÉ")
            logger.info(f"💾 Sauvegarde: {session_dir}")
            
            # Émettre l'info au frontend
            socketio.emit('auto_mode_started', {
                'session_dir': session_dir,
                'message': f'🤖 Mode automatique - Images sauvées dans: {session_dir}'
            })
            
            # Compter les pages
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
            
            logger.info(f"📄 PDF: {total_pages} pages à traiter automatiquement")
            
            auto_detector = SmartAutoDetector()
            page_logs = []  # Logs détaillés par page
            
            for page_num in range(1, min(total_pages + 1, 200)):
                page_start_time = time.time()
                page_log = {
                    'page': page_num,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'processing'
                }
                
                try:
                    logger.info(f"📄 Page {page_num}/{total_pages}: Traitement automatique...")
                    
                    # Analyser les dimensions de la page
                    page_analysis = page_analyzer.analyze_page_dimensions(pdf_path, page_num)
                    optimal_dpi = page_analysis['recommended_dpi']
                    
                    page_log['page_analysis'] = page_analysis
                    page_log['dpi_used'] = optimal_dpi
                    
                    # Convertir la page
                    page_images = convert_from_path(
                        pdf_path, 
                        dpi=optimal_dpi,
                        first_page=page_num,
                        last_page=page_num
                    )
                    
                    if not page_images:
                        page_log['status'] = 'failed'
                        page_log['error'] = 'Conversion PDF échouée'
                        continue
                    
                    page_image = page_images[0]
                    page_array = np.array(page_image)
                    page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
                    
                    page_log['image_size'] = f"{page_cv.shape[1]}x{page_cv.shape[0]}"
                    
                    # **DÉTECTION AUTOMATIQUE INTELLIGENTE**
                    rectangles, best_config = auto_detector.auto_detect_best_config(page_cv, page_num)
                    
                    page_log['config_used'] = best_config['name']
                    page_log['rectangles_found'] = len(rectangles)
                    page_log['rectangles_details'] = []
                    
                    logger.info(f"✅ Page {page_num}: {len(rectangles)} rectangles avec config '{best_config['name']}'")
                    
                    # **SAUVEGARDE AUTOMATIQUE IMMÉDIATE**
                    saved_images = []
                    for rect_idx, rectangle in enumerate(rectangles):
                        artwork_number = rectangle.get('artwork_number')
                        
                        # Sauvegarder en temps réel
                        saved_path = saver.save_rectangle_immediately(
                            page_cv,
                            rectangle,
                            page_num,
                            rect_idx + 1,
                            artwork_number
                        )
                        
                        rect_info = {
                            'rect_id': rect_idx + 1,
                            'artwork_number': artwork_number,
                            'bbox': rectangle.get('bbox'),
                            'area': rectangle.get('area'),
                            'saved_path': saved_path,
                            'filename': os.path.basename(saved_path) if saved_path else None
                        }
                        page_log['rectangles_details'].append(rect_info)
                        
                        if saved_path:
                            saved_images.append(os.path.basename(saved_path))
                            logger.info(f"✅ Image sauvée: {os.path.basename(saved_path)}")
                    
                    page_log['saved_images'] = saved_images
                    page_log['status'] = 'success'
                    page_processing_time = time.time() - page_start_time
                    page_log['processing_time'] = round(page_processing_time, 2)
                    
                    # Sauvegarder le log JSON de cette page
                    page_log_path = os.path.join(session_dir, f"page_{page_num:03d}_log.json")
                    with open(page_log_path, 'w', encoding='utf-8') as f:
                        json.dump(page_log, f, indent=2, ensure_ascii=False)
                    
                    # Émettre la progression avec détails
                    socketio.emit('auto_page_complete', {
                        'page': page_num,
                        'total_pages': total_pages,
                        'rectangles_found': len(rectangles),
                        'config_used': best_config['name'],
                        'saved_count': saver.saved_count,
                        'saved_images': saved_images,
                        'processing_time': page_processing_time,
                        'progress': (page_num / total_pages) * 100,
                        'log_file': f"page_{page_num:03d}_log.json"
                    })
                    
                except Exception as e:
                    page_log['status'] = 'error'
                    page_log['error'] = str(e)
                    page_log['processing_time'] = time.time() - page_start_time
                    logger.error(f"❌ Erreur page {page_num}: {e}")
                    
                    # Sauvegarder le log d'erreur quand même
                    page_log_path = os.path.join(session_dir, f"page_{page_num:03d}_log.json")
                    with open(page_log_path, 'w', encoding='utf-8') as f:
                        json.dump(page_log, f, indent=2, ensure_ascii=False)
                
                page_logs.append(page_log)
            
            # Créer le résumé final avec logs complets
            summary_path = saver.create_summary()
            
            # Sauvegarder les logs complets
            complete_log = {
                'session_info': {
                    'pdf_name': os.path.basename(pdf_path),
                    'session_dir': session_dir,
                    'start_time': datetime.now().isoformat(),
                    'total_pages': total_pages,
                    'total_saved': saver.saved_count,
                    'mode': 'auto_realtime'
                },
                'pages': page_logs,
                'summary': {
                    'successful_pages': len([p for p in page_logs if p['status'] == 'success']),
                    'failed_pages': len([p for p in page_logs if p['status'] in ['failed', 'error']]),
                    'total_rectangles': sum(p.get('rectangles_found', 0) for p in page_logs),
                    'configs_used': list(set(p.get('config_used') for p in page_logs if p.get('config_used')))
                }
            }
            
            complete_log_path = os.path.join(session_dir, "complete_log.json")
            with open(complete_log_path, 'w', encoding='utf-8') as f:
                json.dump(complete_log, f, indent=2, ensure_ascii=False)
            
            # Ouvrir automatiquement le dossier (Windows)
            if os.name == 'nt':
                try:
                    os.startfile(session_dir)
                except Exception as e:
                    logger.warning(f"Impossible d'ouvrir le dossier automatiquement: {e}")
            
            logger.info(f"🎉 MODE AUTOMATIQUE TERMINÉ: {saver.saved_count} images sauvées")
            
            return {
                'success': True,
                'total_saved': saver.saved_count,
                'session_dir': session_dir,
                'summary_path': summary_path,
                'complete_log_path': complete_log_path,
                'saved_files': saver.saved_files,
                'page_logs': page_logs
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur mode automatique: {e}")
            return {'success': False, 'error': str(e)}

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
                
                # **NOUVEAU: ANALYSE AUTOMATIQUE DE LA PAGE**
                logger.info(f"📏 Analyse dimensions page {page_num}...")
                page_analysis = page_analyzer.analyze_page_dimensions(pdf_path, page_num)
                
                optimal_dpi = page_analysis['recommended_dpi']
                detection_params = page_analysis['detection_params']
                
                logger.info(f"📄 Page {page_num}: {page_analysis['page_format']} "
                           f"({page_analysis['width_mm']}×{page_analysis['height_mm']}mm) "
                           f"→ DPI optimal: {optimal_dpi}")
                
                # **CORRECTION 3: Retry avec DPI adaptatif + timeout**
                page_image = None
                retry_count = 0
                max_retries = 2
                # DPI adaptatifs basés sur l'analyse de la page
                dpi_levels = [optimal_dpi, max(150, optimal_dpi // 2), 150]
                
                while retry_count < max_retries and page_image is None:
                    try:
                        current_dpi = dpi_levels[min(retry_count, len(dpi_levels)-1)]
                        logger.info(f"🔄 Page {page_num} - Tentative {retry_count+1}/{max_retries} - DPI {current_dpi} "
                                   f"(estimé: {detection_params['estimated_megapixels']}MP)")
                        
                        # Convertir avec timeout (compatible Windows)
                        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
                        
                        def convert_page():
                            return convert_from_path(
                                pdf_path, 
                                dpi=current_dpi,
                                first_page=page_num,
                                last_page=page_num
                            )
                        
                        # Timeout avec ThreadPoolExecutor (compatible Windows)
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(convert_page)
                            try:
                                page_images = future.result(timeout=30)  # 30 secondes max
                            except FutureTimeoutError:
                                raise TimeoutError("Timeout conversion page")
                        
                        if page_images:
                            page_image = page_images[0]
                            if retry_count > 0:
                                logger.info(f"✅ Page {page_num}: Réussie avec DPI {current_dpi}")
                        else:
                            raise Exception("Aucune image retournée")
                            
                    except (Exception, TimeoutError, FutureTimeoutError) as e:
                        retry_count += 1
                        logger.warning(f"⚠️ Page {page_num} tentative {retry_count}: {e}")
                        
                        if retry_count >= max_retries:
                            logger.error(f"❌ Page {page_num}: Toutes les tentatives échouées")
                            # Envoyer une page vide pour ne pas bloquer
                            socketio.emit('page_results', {
                                'page_number': page_num,
                                'rectangles': [],
                                'rectangles_count': 0,
                                'processing_time': 0.1,
                                'progress_percent': (page_num / total_pages) * 100,
                                'message': f"Page {page_num} échouée - Ignorée",
                                'error': True
                            })
                            break
                
                if page_image is None:
                    continue  # Passer à la page suivante
                
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
                
                # **CORRECTION 2: Ne pas stocker toutes les images en mémoire**
                # Juste garder pour la page courante - économie de RAM massive
                page_data = {
                    'page_number': page_num,
                    'image': page_cv
                }
                # Ne stocker que les 3 dernières pages pour économiser la mémoire
                self.pages.append(page_data)
                if len(self.pages) > 3:
                    self.pages.pop(0)  # Supprimer la plus ancienne
                
                # **DÉTECTER AVEC PARAMÈTRES ADAPTATIFS**
                logger.info(f"🎯 Détection avec paramètres adaptatifs: "
                           f"seuil={detection_params['min_area']}, "
                           f"max_rect={detection_params['max_rectangles']}")
                
                # Passer les paramètres optimisés à la détection AVEC DEBUG
                rectangles = detector.detect_rectangles(
                    page_cv, 
                    sensitivity, 
                    mode,
                    adaptive_params=detection_params,
                    debug_page_num=page_num  # Activer logs détaillés avec numéro de page
                )
                
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
                # **DEBUGGING: Comparaison web vs debug**
                logger.info(f"🔍 COMPARAISON DEBUG - Page {page_num}:")
                logger.info(f"   - Rectangles trouvés: {len(rectangles)}")
                logger.info(f"   - Paramètres utilisés: DPI {current_dpi}, Mode {mode}, Sensibilité {sensitivity}")
                logger.info(f"   - Format page: {page_analysis['page_format']}")
                logger.info(f"   - Seuil aire: {detection_params['min_area']}")
                
                # Log détaillé des rectangles pour debug
                if len(rectangles) > 0:
                    for i, rect in enumerate(rectangles[:3]):  # Max 3 pour éviter spam
                        bbox = rect.get('bbox', {})
                        area = rect.get('area', 0)
                        logger.info(f"   - Rectangle {i+1}: {bbox.get('w', 0)}×{bbox.get('h', 0)}, aire={area:.0f}")
                else:
                    logger.warning(f"   ⚠️ AUCUN RECTANGLE - Page {page_num} problématique!")
                
                socketio.emit('page_results', {
                    'page_number': page_num,
                    'rectangles': rectangles,
                    'rectangles_count': len(rectangles),
                    'processing_time': page_time,
                    'progress_percent': (page_num / total_pages) * 100,
                    'message': f"Page {page_num} terminée - {len(rectangles)} rectangles trouvés",
                    # **NOUVEAU: Debug info pour comprendre les différences**
                    'debug_info': {
                        'dpi_used': current_dpi,
                        'page_format': page_analysis['page_format'],
                        'seuil_aire': detection_params['min_area'],
                        'estimated_mp': detection_params['estimated_megapixels']
                    }
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
                'is_pdf': True
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
# page_analyzer sera défini après la classe PDFPageAnalyzer

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
    
    def detect_rectangles(self, image, sensitivity=50, mode='general', adaptive_params=None, debug_page_num=None):
        """Méthode principale de détection avec différents modes et logs détaillés"""
        logger.info(f"🔍 Mode: {mode}, Sensibilité: {sensitivity}")
        
        # **NOUVEAU: Debug détaillé avec numéro de page**
        if debug_page_num:
            logger.info(f"🐛 DEBUG PAGE {debug_page_num} - Début analyse détaillée")
        
        try:
            # **ÉTAPE 1: ANALYSE DE L'IMAGE D'ENTRÉE**
            height, width = image.shape[:2]
            total_pixels = height * width
            logger.info(f"📐 Image: {width}×{height} = {total_pixels:,} pixels ({total_pixels/1000000:.1f}MP)")
            
            # Prétraitement adaptatif selon le mode
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            logger.info(f"✅ Conversion en niveaux de gris terminée")
            
            # **ADAPTATION SELON LE MODE AVEC LOGS**
            if mode == 'documents':
                logger.info("📄 Mode DOCUMENTS - Optimisé pour docs multiples")
                denoised = cv2.fastNlMeansDenoising(gray, h=10)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16,16))
                enhanced = clahe.apply(denoised)
                canny_low = 5
                canny_high = 20
                min_area_divisor = 400
            elif mode == 'high_contrast':
                logger.info("🎯 Mode HIGH_CONTRAST - Optimisé pour objets contrastés")
                denoised = cv2.GaussianBlur(gray, (3, 3), 0)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = clahe.apply(denoised)
                canny_low = max(30, sensitivity // 2)
                canny_high = max(80, sensitivity * 2)
                min_area_divisor = 100
            else:  # mode general
                logger.info("⚖️ Mode GENERAL - Équilibré")
                denoised = cv2.fastNlMeansDenoising(gray)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                enhanced = clahe.apply(denoised)
                canny_low = max(10, sensitivity // 2)
                canny_high = max(30, sensitivity)
                min_area_divisor = 200
            
            logger.info(f"🎛️ Paramètres Canny: {canny_low}-{canny_high}, Diviseur aire: {min_area_divisor}")
            
            # **ÉTAPE 2: DÉTECTION DE BORDS MULTIPLE AVEC LOGS**
            logger.info("🔄 Étape 2: Détection de bords...")
            
            # Détection de bords sensible
            edges_sensitive = cv2.Canny(enhanced, canny_low, canny_high)
            edge_pixels = cv2.countNonZero(edges_sensitive)
            logger.info(f"   📊 Bords détectés: {edge_pixels:,} pixels ({edge_pixels/total_pixels*100:.2f}%)")
            
            # Gradient morphologique
            kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
            _, gradient_thresh = cv2.threshold(gradient, sensitivity // 4, 255, cv2.THRESH_BINARY)
            gradient_pixels = cv2.countNonZero(gradient_thresh)
            logger.info(f"   📊 Gradients: {gradient_pixels:,} pixels ({gradient_pixels/total_pixels*100:.2f}%)")
            
            # Seuillage adaptatif
            block_size = 15 if mode == 'documents' else 11
            adaptive_thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, block_size, 2
            )
            adaptive_thresh = cv2.bitwise_not(adaptive_thresh)
            adaptive_pixels = cv2.countNonZero(adaptive_thresh)
            logger.info(f"   📊 Seuillage adaptatif: {adaptive_pixels:,} pixels ({adaptive_pixels/total_pixels*100:.2f}%)")
            
            # Combiner toutes les techniques
            combined = cv2.bitwise_or(edges_sensitive, gradient_thresh)
            combined = cv2.bitwise_or(combined, adaptive_thresh)
            combined_pixels = cv2.countNonZero(combined)
            logger.info(f"   📊 Combiné final: {combined_pixels:,} pixels ({combined_pixels/total_pixels*100:.2f}%)")
            
            if combined_pixels < total_pixels * 0.001:  # Moins de 0.1% de pixels détectés
                logger.warning(f"⚠️ TRÈS PEU DE BORDS DÉTECTÉS - Possible image trop homogène ou seuils inadaptés")
            
            # **ÉTAPE 3: MORPHOLOGIE AVEC LOGS**
            logger.info("🔄 Étape 3: Morphologie...")
            if mode == 'documents':
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=2)
            else:
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close)
            
            morph_pixels = cv2.countNonZero(combined)
            logger.info(f"   📊 Après morphologie: {morph_pixels:,} pixels")
            
            # **ÉTAPE 4: DÉTECTION DES CONTOURS AVEC LOGS DÉTAILLÉS**
            logger.info("🔄 Étape 4: Détection des contours...")
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            logger.info(f"   📊 Contours bruts trouvés: {len(contours)}")
            
            if len(contours) == 0:
                logger.error(f"❌ AUCUN CONTOUR DÉTECTÉ - Problème dans la détection de bords")
                logger.error(f"   - Pixels de bords: {edge_pixels:,}")
                logger.error(f"   - Sensibilité utilisée: {sensitivity}")
                logger.error(f"   - Mode: {mode}")
                logger.error(f"   - Paramètres Canny: {canny_low}-{canny_high}")
                return []
            
            # **NOUVEAU: SEUILS INTELLIGENTS AVEC ANALYSE DE PAGE ET LOGS**
            rectangles = []
            
            if adaptive_params:
                # Utiliser les paramètres calculés spécifiquement pour cette page
                min_area = adaptive_params['min_area']
                max_rectangles_limit = adaptive_params['max_rectangles']
                logger.info(f"🎯 Paramètres adaptatifs: aire_min={min_area:.0f}, "
                           f"max_rect={max_rectangles_limit}, "
                           f"taille_réelle={adaptive_params['estimated_megapixels']}MP")
            else:
                # Fallback : seuils adaptatifs basiques
                image_megapixels = total_pixels / 1000000
                if image_megapixels > 50:
                    min_area_divisor = min_area_divisor * 2
                    max_rectangles_limit = 50
                elif image_megapixels > 20:
                    max_rectangles_limit = 40
                else:
                    max_rectangles_limit = 30
                
                min_area = total_pixels / min_area_divisor
                logger.info(f"🔍 Mode fallback - Image {image_megapixels:.1f}MP, seuil={min_area:.0f}")
            
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            logger.info(f"📏 Seuil aire minimale: {min_area:.0f} pixels")
            
            # **ÉTAPE 5: ANALYSE DÉTAILLÉE DE CHAQUE CONTOUR**
            logger.info("🔄 Étape 5: Analyse des contours...")
            
            contours_analyzed = 0
            contours_too_small = 0
            contours_not_4_corners = 0
            contours_not_convex = 0
            contours_low_ratio = 0
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                contours_analyzed += 1
                
                # Log détaillé pour les 10 premiers contours
                if i < 10 or debug_page_num:
                    logger.info(f"   🔍 Contour {i+1}: aire={area:.0f} (seuil={min_area:.0f})")
                
                if area < min_area:
                    contours_too_small += 1
                    if i < 5 or debug_page_num:  # Log détaillé pour debug
                        logger.info(f"      ❌ Trop petit: {area:.0f} < {min_area:.0f}")
                    continue
                
                # Approximation progressive AVEC LOGS
                epsilon_steps = [0.003, 0.005, 0.008, 0.012, 0.015] if mode == 'documents' else [0.005, 0.01, 0.015, 0.02, 0.025]
                found_rectangle = False
                
                for j, epsilon_mult in enumerate(epsilon_steps):
                    epsilon = epsilon_mult * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    if i < 5 or debug_page_num:
                        logger.info(f"      🔄 Approx {j+1}: epsilon={epsilon_mult}, coins={len(approx)}")
                    
                    if len(approx) == 4 and cv2.isContourConvex(approx):
                        rectangles.append({
                            'id': len(rectangles),
                            'contour': contour,
                            'corners': approx.reshape(4, 2),
                            'area': area,
                            'bbox': cv2.boundingRect(contour),
                            'mode': mode
                        })
                        found_rectangle = True
                        if i < 5 or debug_page_num:
                            logger.info(f"      ✅ Rectangle validé!")
                        break
                    elif len(approx) != 4:
                        contours_not_4_corners += 1
                    elif not cv2.isContourConvex(approx):
                        contours_not_convex += 1
                
                if not found_rectangle:
                    # Fallback rectangle englobant AVEC LOGS
                    x, y, w, h = cv2.boundingRect(contour)
                    bbox_area = w * h
                    area_ratio = area / bbox_area if bbox_area > 0 else 0
                    ratio_threshold = 0.5 if mode == 'documents' else 0.6
                    
                    if i < 5 or debug_page_num:
                        logger.info(f"      🔄 Fallback bbox: ratio={area_ratio:.2f} (seuil={ratio_threshold})")
                    
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
                        if i < 5 or debug_page_num:
                            logger.info(f"      ✅ Rectangle bbox accepté!")
                    else:
                        contours_low_ratio += 1
                        if i < 5 or debug_page_num:
                            logger.info(f"      ❌ Bbox rejeté: ratio trop faible")
                
                # **LIMITE INTELLIGENTE AVEC ANALYSE DE PAGE**
                if adaptive_params:
                    max_rectangles = adaptive_params['max_rectangles']
                else:
                    # Fallback
                    image_megapixels = (image.shape[0] * image.shape[1]) / 1000000
                    if image_megapixels > 50:
                        max_rectangles = 50
                    elif mode == 'documents':
                        max_rectangles = 30
                    else:
                        max_rectangles = 20
                
                if len(rectangles) >= max_rectangles:
                    logger.info(f"📊 Limite optimale atteinte: {max_rectangles} rectangles "
                               f"(adapté à cette page)")
                    break
            
            # **ÉTAPE 6: STATISTIQUES DÉTAILLÉES**
            logger.info(f"📊 STATISTIQUES DE DÉTECTION:")
            logger.info(f"   - Contours analysés: {contours_analyzed}")
            logger.info(f"   - Rejetés (trop petits): {contours_too_small}")
            logger.info(f"   - Rejetés (pas 4 coins): {contours_not_4_corners}")
            logger.info(f"   - Rejetés (pas convexes): {contours_not_convex}")
            logger.info(f"   - Rejetés (ratio faible): {contours_low_ratio}")
            logger.info(f"   - Rectangles validés: {len(rectangles)}")
            
            if len(rectangles) == 0:
                logger.warning(f"⚠️ AUCUN RECTANGLE DÉTECTÉ!")
                logger.warning(f"   - Seuil aire peut être trop strict: {min_area:.0f}")
                logger.warning(f"   - Plus grand contour: {cv2.contourArea(contours[0]):.0f}")
                logger.warning(f"   - Ratio: {cv2.contourArea(contours[0])/min_area:.2f}")
                
                # Suggestion d'ajustement
                if cv2.contourArea(contours[0]) > min_area * 0.5:
                    logger.warning(f"💡 SUGGESTION: Réduire la sensibilité ou ajuster le mode")
                else:
                    logger.warning(f"💡 SUGGESTION: Vérifier la qualité de l'image ou le prétraitement")
            
            # Filtrage des chevauchements
            rectangles = self.filter_overlapping_rectangles(rectangles)
            logger.info(f"✅ {len(rectangles)} rectangles après filtrage des doublons")
            
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
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
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

class SmartAutoDetector:
    """
    Détecteur intelligent qui teste automatiquement plusieurs configurations
    et choisit la meilleure pour chaque page
    """
    
    def __init__(self):
        self.detection_cache = {}
        
    def auto_detect_best_config(self, image, page_num=None):
        """
        Teste automatiquement plusieurs configurations et retourne la meilleure
        """
        logger.info(f"🤖 AUTO-DÉTECTION INTELLIGENTE - Page {page_num if page_num else 'image'}")
        
        # Analyser l'image pour déterminer ses caractéristiques
        image_stats = self._analyze_image_characteristics(image)
        
        # Configurations à tester automatiquement
        test_configs = self._generate_smart_configs(image_stats)
        
        best_result = None
        best_score = 0
        best_config = None
        
        for config in test_configs:
            try:
                # Tester cette configuration
                rectangles = self._test_configuration(image, config)
                
                # Calculer un score de qualité
                score = self._calculate_detection_score(rectangles, image_stats)
                
                logger.info(f"   Config {config['name']}: {len(rectangles)} rectangles, score={score:.2f}")
                
                if score > best_score:
                    best_score = score
                    best_result = rectangles
                    best_config = config
                    
            except Exception as e:
                logger.warning(f"   Config {config['name']} échouée: {e}")
                continue
        
        logger.info(f"✅ MEILLEURE CONFIG: {best_config['name']} avec {len(best_result)} rectangles")
        return best_result, best_config
    
    def _analyze_image_characteristics(self, image):
        """Analyse les caractéristiques de l'image pour adapter la détection"""
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculer des statistiques sur l'image
        stats = {
            'width': width,
            'height': height,
            'megapixels': (width * height) / 1000000,
            'aspect_ratio': width / height,
        }
        
        # Analyser le contraste
        stats['std_dev'] = np.std(gray)
        stats['mean_brightness'] = np.mean(gray)
        
        # Détecter le niveau de bruit
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        stats['noise_level'] = laplacian_var
        
        # Analyser la distribution des couleurs
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        stats['histogram_entropy'] = -np.sum(hist[hist > 0] * np.log2(hist[hist > 0] + 1e-10))
        
        # Détection de bords préliminaire
        edges = cv2.Canny(gray, 50, 150)
        stats['edge_density'] = np.count_nonzero(edges) / (width * height)
        
        # Classifier le type d'image
        if stats['std_dev'] < 30:
            stats['image_type'] = 'low_contrast'
        elif stats['std_dev'] > 80:
            stats['image_type'] = 'high_contrast'
        else:
            stats['image_type'] = 'normal_contrast'
            
        if stats['edge_density'] > 0.15:
            stats['complexity'] = 'complex'
        elif stats['edge_density'] < 0.05:
            stats['complexity'] = 'simple'
        else:
            stats['complexity'] = 'moderate'
        
        logger.info(f"📊 Analyse image: {stats['image_type']}, complexité={stats['complexity']}, "
                   f"contraste={stats['std_dev']:.1f}, bords={stats['edge_density']:.3f}")
        
        return stats
    
    def _generate_smart_configs(self, image_stats):
        """Génère des configurations adaptées aux caractéristiques de l'image"""
        configs = []
        
        # Configuration de base selon le type d'image
        if image_stats['image_type'] == 'low_contrast':
            # Pour images à faible contraste
            configs.extend([
                {'name': 'low_contrast_enhanced', 'mode': 'documents', 'sensitivity': 70, 
                 'preprocessing': 'heavy_enhance'},
                {'name': 'low_contrast_adaptive', 'mode': 'general', 'sensitivity': 60,
                 'preprocessing': 'adaptive_enhance'},
                {'name': 'low_contrast_gradient', 'mode': 'documents', 'sensitivity': 80,
                 'preprocessing': 'gradient_boost'}
            ])
        elif image_stats['image_type'] == 'high_contrast':
            # Pour images à fort contraste
            configs.extend([
                {'name': 'high_contrast_standard', 'mode': 'high_contrast', 'sensitivity': 40,
                 'preprocessing': 'minimal'},
                {'name': 'high_contrast_precise', 'mode': 'high_contrast', 'sensitivity': 30,
                 'preprocessing': 'denoise_light'},
                {'name': 'high_contrast_sensitive', 'mode': 'general', 'sensitivity': 50,
                 'preprocessing': 'standard'}
            ])
        else:
            # Pour images normales
            configs.extend([
                {'name': 'normal_balanced', 'mode': 'general', 'sensitivity': 50,
                 'preprocessing': 'standard'},
                {'name': 'normal_documents', 'mode': 'documents', 'sensitivity': 60,
                 'preprocessing': 'enhance_light'},
                {'name': 'normal_sensitive', 'mode': 'general', 'sensitivity': 70,
                 'preprocessing': 'adaptive'}
            ])
        
        # Ajouter des configs selon la complexité
        if image_stats['complexity'] == 'complex':
            configs.append({'name': 'complex_filtering', 'mode': 'documents', 'sensitivity': 40,
                          'preprocessing': 'heavy_denoise'})
        elif image_stats['complexity'] == 'simple':
            configs.append({'name': 'simple_fast', 'mode': 'high_contrast', 'sensitivity': 60,
                          'preprocessing': 'minimal'})
        
        return configs
    
    def _test_configuration(self, image, config):
        """Teste une configuration spécifique"""
        # Appliquer le prétraitement approprié
        processed_image = self._apply_preprocessing(image, config['preprocessing'])
        
        # Créer un détecteur temporaire pour ce test
        temp_detector = RectangleDetector()
        
        # Adapter les paramètres selon la config
        height, width = processed_image.shape[:2]
        total_pixels = height * width
        
        # Paramètres adaptatifs intelligents
        adaptive_params = {
            'min_area': total_pixels / 500 if config['mode'] == 'documents' else total_pixels / 300,
            'max_rectangles': 30 if config['mode'] == 'documents' else 20,
            'estimated_megapixels': total_pixels / 1000000,
            'min_area_divisor': 500 if config['mode'] == 'documents' else 300
        }
        
        # Détecter avec cette configuration
        rectangles = temp_detector.detect_rectangles(
            processed_image,
            config['sensitivity'],
            config['mode'],
            adaptive_params=adaptive_params
        )
        
        return rectangles
    
    def _apply_preprocessing(self, image, preprocessing_type):
        """Applique le prétraitement spécifique"""
        if preprocessing_type == 'minimal':
            return image
            
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if preprocessing_type == 'heavy_enhance':
            # Amélioration forte pour images faible contraste
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16,16))
            enhanced = clahe.apply(denoised)
            # Augmenter le contraste
            enhanced = cv2.convertScaleAbs(enhanced, alpha=1.5, beta=10)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
        elif preprocessing_type == 'adaptive_enhance':
            # Amélioration adaptative
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
        elif preprocessing_type == 'gradient_boost':
            # Boost des gradients
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient = np.sqrt(grad_x**2 + grad_y**2)
            gradient = np.uint8(255 * gradient / gradient.max())
            combined = cv2.addWeighted(gray, 0.7, gradient, 0.3, 0)
            return cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)
            
        elif preprocessing_type == 'denoise_light':
            # Débruitage léger
            denoised = cv2.GaussianBlur(image, (3, 3), 0)
            return denoised
            
        elif preprocessing_type == 'heavy_denoise':
            # Débruitage fort
            denoised = cv2.fastNlMeansDenoising(gray, h=20)
            denoised = cv2.medianBlur(denoised, 5)
            return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
            
        elif preprocessing_type == 'standard':
            # Traitement standard
            denoised = cv2.fastNlMeansDenoising(gray)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
        elif preprocessing_type == 'enhance_light':
            # Amélioration légère
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
        else:  # 'adaptive'
            # Traitement adaptatif basé sur l'histogramme
            hist, _ = np.histogram(gray.flatten(), 256, [0, 256])
            cdf = hist.cumsum()
            cdf_normalized = cdf * 255 / cdf[-1]
            equalized = np.interp(gray.flatten(), range(256), cdf_normalized).reshape(gray.shape).astype(np.uint8)
            return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
    
    def _calculate_detection_score(self, rectangles, image_stats):
        """Calcule un score de qualité pour les rectangles détectés"""
        if len(rectangles) == 0:
            return 0
        
        score = 0
        total_area = image_stats['width'] * image_stats['height']
        
        # Score basé sur le nombre de rectangles (pénaliser trop ou trop peu)
        if 1 <= len(rectangles) <= 30:
            score += 30  # Nombre raisonnable
        elif len(rectangles) > 30:
            score += 30 - (len(rectangles) - 30) * 0.5  # Pénaliser l'excès
        
        # Score basé sur la couverture
        covered_area = 0
        for rect in rectangles:
            if 'area' in rect:
                covered_area += rect['area']
        
        coverage_ratio = covered_area / total_area
        if 0.1 <= coverage_ratio <= 0.8:
            score += 20 * (1 - abs(coverage_ratio - 0.4))  # Optimal autour de 40%
        
        # Score basé sur la distribution des tailles
        if rectangles:
            areas = [r['area'] for r in rectangles if 'area' in r]
            if areas:
                std_area = np.std(areas)
                mean_area = np.mean(areas)
                cv_area = std_area / mean_area if mean_area > 0 else 0
                
                # Préférer une certaine uniformité
                if cv_area < 2:  # Coefficient de variation < 2
                    score += 10
        
        # Score basé sur les ratios d'aspect
        good_ratios = 0
        for rect in rectangles:
            if 'bbox' in rect:
                bbox = rect['bbox']
                if isinstance(bbox, dict):
                    w, h = bbox.get('w', 1), bbox.get('h', 1)
                else:
                    _, _, w, h = bbox
                ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 100
                if 1 <= ratio <= 3:  # Ratio raisonnable
                    good_ratios += 1
        
        score += (good_ratios / len(rectangles)) * 20 if rectangles else 0
        
        # Bonus pour détection de haute confiance
        high_confidence = sum(1 for r in rectangles if r.get('confidence', 0) > 0.7)
        score += (high_confidence / len(rectangles)) * 10 if rectangles else 0
        
        return score

# Initialiser les détecteurs
detector = RectangleDetector()
artwork_detector = ArtworkNumberDetector()
smart_auto_detector = SmartAutoDetector()
realtime_saver = RealtimeSaver()

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


@app.route('/upload_auto', methods=['POST'])
def upload_auto_complete():
    """MODE AUTOMATIQUE COMPLET - Fait tout automatiquement avec sauvegarde et logs"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            logger.info(f"🤖 MODE AUTOMATIQUE COMPLET activé pour {filename}")
            
            if is_pdf(filename):
                # Nettoyer les données précédentes
                pdf_processor.clear()
                pdf_processor.original_filename = filename.replace('.pdf', '')
                
                # Traitement automatique complet
                def process_auto_complete():
                    try:
                        result = pdf_processor.process_pdf_auto_with_realtime_save(filepath)
                        pdf_processor.current_result = result
                        
                        socketio.emit('auto_complete', {
                            'success': result['success'],
                            'total_saved': result.get('total_saved', 0),
                            'session_dir': result.get('session_dir'),
                            'message': f'🎉 Mode automatique terminé! {result.get("total_saved", 0)} images sauvées',
                            'complete_log_path': result.get('complete_log_path')
                        })
                        
                    except Exception as e:
                        logger.error(f"Erreur auto complet: {e}")
                        socketio.emit('auto_error', {'error': str(e)})
                
                # Démarrer dans un thread
                import threading
                thread = threading.Thread(target=process_auto_complete)
                thread.start()
                
                return jsonify({
                    'success': True,
                    'message': '🤖 Mode automatique complet démarré',
                    'filename': filename,
                    'info': 'Détection automatique + extraction + sauvegarde avec logs JSON',
                    'auto_mode': True,
                    'features': [
                        'Détection automatique intelligente',
                        'Extraction et sauvegarde en temps réel', 
                        'Logs JSON détaillés par page',
                        'Ouverture automatique du dossier',
                        'Résumé HTML avec galerie'
                    ]
                })
            else:
                # Pour une image simple, utiliser aussi l'auto-détection avec sauvegarde
                image = cv2.imread(filepath)
                if image is None:
                    return jsonify({'error': 'Impossible de lire l\'image'}), 400
                
                # Initialiser le saver pour image simple
                saver = RealtimeSaver()
                session_dir = saver.create_session_folder(filename)
                
                rectangles, best_config = smart_auto_detector.auto_detect_best_config(image)
                
                # Sauvegarder les rectangles détectés
                saved_images = []
                for rect_idx, rectangle in enumerate(rectangles):
                    artwork_number = rectangle.get('artwork_number')
                    saved_path = saver.save_rectangle_immediately(
                        image, rectangle, 1, rect_idx + 1, artwork_number
                    )
                    if saved_path:
                        saved_images.append(os.path.basename(saved_path))
                
                # Créer le log pour l'image
                image_log = {
                    'filename': filename,
                    'config_used': best_config['name'],
                    'rectangles_found': len(rectangles),
                    'saved_images': saved_images,
                    'session_dir': session_dir
                }
                
                log_path = os.path.join(session_dir, "image_log.json")
                with open(log_path, 'w', encoding='utf-8') as f:
                    json.dump(image_log, f, indent=2, ensure_ascii=False)
                
                # Ouvrir le dossier
                if os.name == 'nt':
                    try:
                        os.startfile(session_dir)
                    except:
                        pass
                
                logger.info(f"✅ Image traitée: {len(rectangles)} rectangles, {len(saved_images)} sauvées")
                
                return jsonify({
                    'filename': filename,
                    'rectangles_count': len(rectangles),
                    'saved_count': len(saved_images),
                    'config_used': best_config['name'],
                    'session_dir': session_dir,
                    'saved_images': saved_images,
                    'auto_mode': True
                })
        
        return jsonify({'error': 'Format de fichier non supporté'}), 400
        
    except Exception as e:
        logger.error(f"Erreur mode automatique: {str(e)}")
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
            logger.warning(f"⚠️ Aucune image trouvée dans {filename}")
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

@app.route('/debug_page/<filename>/<int:page_number>')
def debug_specific_page(filename, page_number):
    """Endpoint pour débugger une page spécifique d'un PDF"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🔍 DEBUG Page {page_number} de {filename}")
        
        # Paramètres
        sensitivity = int(request.args.get('sensitivity', 50))
        mode = request.args.get('mode', 'general')
        dpi = int(request.args.get('dpi', 300))
        
        try:
            # Convertir juste cette page
            page_images = convert_from_path(
                filepath, 
                dpi=dpi,
                first_page=page_number,
                last_page=page_number
            )
            
            if not page_images:
                return jsonify({'error': f'Impossible de convertir la page {page_number}'}), 400
                
            page_image = page_images[0]
            
            # Convertir pour OpenCV
            page_array = np.array(page_image)
            page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
            
            # **ANALYSER AVEC LE NOUVEAU SYSTÈME ADAPTATIF**
            logger.info(f"📏 Analyse automatique page {page_number}...")
            page_analysis = page_analyzer.analyze_page_dimensions(filepath, page_number)
            
            start_time = time.time()
            rectangles = detector.detect_rectangles(
                page_cv, 
                sensitivity, 
                mode,
                adaptive_params=page_analysis['detection_params'],
                debug_page_num=page_number  # Debug pour endpoint de test
            )
            processing_time = time.time() - start_time
            
            # Convertir pour JSON
            for rect in rectangles:
                if 'corners' in rect and hasattr(rect['corners'], 'tolist'):
                    rect['corners'] = rect['corners'].tolist()
                if 'bbox' in rect and isinstance(rect['bbox'], tuple):
                    x, y, w, h = rect['bbox']
                    rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                if 'contour' in rect:
                    del rect['contour']
                for key, value in rect.items():
                    if hasattr(value, 'tolist'):
                        rect[key] = value.tolist()
                    elif hasattr(value, 'item'):
                        rect[key] = value.item()
            
            # Retourner les détails de debug avec analyse de page
            return jsonify({
                'success': True,
                'page_number': page_number,
                'filename': filename,
                'image_size': f"{page_cv.shape[1]}x{page_cv.shape[0]}",
                'image_megapixels': round((page_cv.shape[0] * page_cv.shape[1]) / 1000000, 1),
                'dpi_used': dpi,
                'sensitivity': sensitivity,
                'mode': mode,
                'processing_time': round(processing_time, 2),
                'rectangles_found': len(rectangles),
                'rectangles': rectangles,
                # **NOUVEAU: Analyse intelligente de la page**
                'page_analysis': {
                    'physical_size': f"{page_analysis['width_mm']}×{page_analysis['height_mm']}mm",
                    'page_format': page_analysis['page_format'],
                    'area_mm2': page_analysis['area_mm2'],
                    'recommended_dpi': page_analysis['recommended_dpi'],
                    'dpi_actually_used': dpi,
                    'optimal_vs_used': 'Optimal' if dpi == page_analysis['recommended_dpi'] else f"Dégradé ({page_analysis['recommended_dpi']} → {dpi})"
                },
                'detection_params': page_analysis['detection_params'],
                'debug_info': {
                    'total_pixels': page_cv.shape[0] * page_cv.shape[1],
                    'adaptive_min_area': page_analysis['detection_params']['min_area'],
                    'adaptive_max_rectangles': page_analysis['detection_params']['max_rectangles'],
                    'analysis_cache_hit': f"{filepath}_{page_number}" in page_analyzer.page_cache
                }
            })
            
        except Exception as e:
            logger.error(f"Erreur debug page {page_number}: {e}")
            return jsonify({'error': f'Erreur traitement page: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Erreur debug: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/debug_visual/<filename>/<int:page_number>')
def debug_visual_page(filename, page_number):
    """Endpoint pour débugger visuellement une page avec images intermédiaires"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🎨 DEBUG VISUEL Page {page_number} de {filename}")
        
        # Paramètres
        sensitivity = int(request.args.get('sensitivity', 50))
        mode = request.args.get('mode', 'high_contrast')
        dpi = int(request.args.get('dpi', 300))
        
        try:
            # Convertir la page
            page_images = convert_from_path(
                filepath, 
                dpi=dpi,
                first_page=page_number,
                last_page=page_number
            )
            
            if not page_images:
                return jsonify({'error': f'Impossible de convertir la page {page_number}'}), 400
                
            page_image = page_images[0]
            page_array = np.array(page_image)
            page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
            
            # Analyser la page
            page_analysis = page_analyzer.analyze_page_dimensions(filepath, page_number)
            detection_params = page_analysis['detection_params']
            
            logger.info(f"🎨 Génération des images de debug...")
            
            # **CRÉER LES IMAGES INTERMÉDIAIRES**
            debug_images = {}
            
            # 1. Image originale
            debug_images['01_original'] = page_cv.copy()
            
            # 2. Niveaux de gris
            gray = cv2.cvtColor(page_cv, cv2.COLOR_BGR2GRAY)
            debug_images['02_gray'] = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            
            # 3. Débruitage selon le mode
            if mode == 'documents':
                denoised = cv2.fastNlMeansDenoising(gray, h=10)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16,16))
                canny_low, canny_high = 5, 20
            elif mode == 'high_contrast':
                denoised = cv2.GaussianBlur(gray, (3, 3), 0)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                canny_low = max(30, sensitivity // 2)
                canny_high = max(80, sensitivity * 2)
            else:  # general
                denoised = cv2.fastNlMeansDenoising(gray)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                canny_low = max(10, sensitivity // 2)
                canny_high = max(30, sensitivity)
            
            enhanced = clahe.apply(denoised)
            debug_images['03_enhanced'] = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
            # 4. Détection de bords
            edges = cv2.Canny(enhanced, canny_low, canny_high)
            debug_images['04_edges'] = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            
            # 5. Gradient morphologique
            kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
            _, gradient_thresh = cv2.threshold(gradient, sensitivity // 4, 255, cv2.THRESH_BINARY)
            debug_images['05_gradient'] = cv2.cvtColor(gradient_thresh, cv2.COLOR_GRAY2BGR)
            
            # 6. Seuillage adaptatif
            block_size = 15 if mode == 'documents' else 11
            adaptive_thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, block_size, 2
            )
            adaptive_thresh = cv2.bitwise_not(adaptive_thresh)
            debug_images['06_adaptive'] = cv2.cvtColor(adaptive_thresh, cv2.COLOR_GRAY2BGR)
            
            # 7. Combiné
            combined = cv2.bitwise_or(edges, gradient_thresh)
            combined = cv2.bitwise_or(combined, adaptive_thresh)
            debug_images['07_combined'] = cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)
            
            # 8. Après morphologie
            if mode == 'documents':
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                morphed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=2)
            else:
                kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                morphed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close)
            
            debug_images['08_morphed'] = cv2.cvtColor(morphed, cv2.COLOR_GRAY2BGR)
            
            # 9. Contours détectés
            contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours_img = page_cv.copy()
            cv2.drawContours(contours_img, contours, -1, (0, 255, 0), 2)
            debug_images['09_contours'] = contours_img
            
            # 10. Rectangles finaux
            rectangles = detector.detect_rectangles(
                page_cv, 
                sensitivity, 
                mode,
                adaptive_params=detection_params,
                debug_page_num=page_number
            )
            
            final_img = page_cv.copy()
            for i, rect in enumerate(rectangles):
                if 'corners' in rect:
                    corners = rect['corners']
                    if isinstance(corners, list):
                        corners = np.array(corners, dtype=np.int32)
                    cv2.polylines(final_img, [corners], True, (0, 0, 255), 3)
                    
                    # Numéroter les rectangles
                    if len(corners) > 0:
                        center_x = int(np.mean(corners[:, 0]))
                        center_y = int(np.mean(corners[:, 1]))
                        cv2.putText(final_img, str(i+1), (center_x, center_y), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
            
            debug_images['10_final_rectangles'] = final_img
            
            # **SAUVEGARDER TOUTES LES IMAGES DANS UN ZIP**
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for img_name, img_data in debug_images.items():
                    # Convertir en PNG
                    _, buffer = cv2.imencode('.png', img_data)
                    
                    # Nom de fichier explicite
                    zip_filename = f"{img_name}_{filename.replace('.pdf', '')}_page-{page_number:03d}.png"
                    
                    # Ajouter au ZIP
                    zip_file.writestr(zip_filename, buffer.tobytes())
                
                # Ajouter un fichier de statistiques
                stats_content = f"""DEBUG VISUEL - Page {page_number}
===========================================

PARAMÈTRES:
- Fichier: {filename}
- Page: {page_number}
- Mode: {mode}
- Sensibilité: {sensitivity}
- DPI: {dpi}

ANALYSE AUTOMATIQUE:
- Format: {page_analysis['page_format']}
- Taille: {page_analysis['width_mm']}×{page_analysis['height_mm']}mm
- DPI recommandé: {page_analysis['recommended_dpi']}
- Seuil aire: {detection_params['min_area']} pixels
- Max rectangles: {detection_params['max_rectangles']}

RÉSULTATS:
- Contours bruts: {len(contours)}
- Rectangles finaux: {len(rectangles)}

IMAGES INCLUSES:
01_original.png - Image originale
02_gray.png - Conversion niveaux de gris
03_enhanced.png - Amélioration contraste (CLAHE)
04_edges.png - Détection de bords (Canny)
05_gradient.png - Gradient morphologique
06_adaptive.png - Seuillage adaptatif
07_combined.png - Combinaison des techniques
08_morphed.png - Après morphologie
09_contours.png - Contours détectés (vert)
10_final_rectangles.png - Rectangles finaux (rouge, numérotés)

CONSEILS DEBUGGING:
- Si 04_edges est très vide → Augmenter sensibilité ou changer mode
- Si 09_contours a beaucoup de contours mais 10_final_rectangles est vide → Seuil trop strict
- Si les contours ne suivent pas bien les formes → Essayer mode 'documents'
"""
                
                zip_file.writestr(f"DEBUG_STATS_page-{page_number:03d}.txt", stats_content)
            
            zip_buffer.seek(0)
            
            logger.info(f"✅ Images de debug générées: {len(debug_images)} étapes")
            
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'debug_visual_{filename.replace(".pdf", "")}_page-{page_number:03d}.zip'
            )
            
        except Exception as e:
            logger.error(f"Erreur debug visuel: {e}")
            return jsonify({'error': f'Erreur traitement: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Erreur debug visuel: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/debug_missing_rectangles/<filename>/<int:page_number>')
def debug_missing_rectangles(filename, page_number):
    """Endpoint spécialisé pour comprendre pourquoi des rectangles sont manqués"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🔍 DEBUG RECTANGLES MANQUÉS - Page {page_number}")
        
        # Test avec PLUSIEURS configurations
        test_configs = [
            {'mode': 'high_contrast', 'sensitivity': 30, 'dpi': 300},
            {'mode': 'high_contrast', 'sensitivity': 50, 'dpi': 300},
            {'mode': 'high_contrast', 'sensitivity': 70, 'dpi': 300},
            {'mode': 'documents', 'sensitivity': 50, 'dpi': 300},
            {'mode': 'general', 'sensitivity': 50, 'dpi': 300},
            {'mode': 'high_contrast', 'sensitivity': 50, 'dpi': 400},
            {'mode': 'high_contrast', 'sensitivity': 50, 'dpi': 200},
        ]
        
        results = []
        
        for config in test_configs:
            try:
                logger.info(f"🧪 Test: Mode={config['mode']}, Sens={config['sensitivity']}, DPI={config['dpi']}")
                
                # Convertir la page
                page_images = convert_from_path(
                    filepath, 
                    dpi=config['dpi'],
                    first_page=page_number,
                    last_page=page_number
                )
                
                if not page_images:
                    continue
                    
                page_image = page_images[0]
                page_array = np.array(page_image)
                page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
                
                # Analyser la page
                page_analysis = page_analyzer.analyze_page_dimensions(filepath, page_number)
                
                # **OVERRIDE des paramètres pour forcer la détection**
                custom_params = page_analysis['detection_params'].copy()
                
                # Réduire drastiquement le seuil d'aire pour capturer plus de rectangles
                custom_params['min_area'] = custom_params['min_area'] // 4  # Diviser par 4
                custom_params['max_rectangles'] = 20  # Permettre plus de rectangles
                
                logger.info(f"   Seuil aire réduit: {custom_params['min_area']} (était {page_analysis['detection_params']['min_area']})")
                
                # Détecter avec paramètres modifiés
                start_time = time.time()
                rectangles = detector.detect_rectangles(
                    page_cv, 
                    config['sensitivity'], 
                    config['mode'],
                    adaptive_params=custom_params,
                    debug_page_num=page_number
                )
                processing_time = time.time() - start_time
                
                # Convertir pour JSON
                for rect in rectangles:
                    if 'corners' in rect and hasattr(rect['corners'], 'tolist'):
                        rect['corners'] = rect['corners'].tolist()
                    if 'bbox' in rect and isinstance(rect['bbox'], tuple):
                        x, y, w, h = rect['bbox']
                        rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                    if 'contour' in rect:
                        del rect['contour']
                    for key, value in rect.items():
                        if hasattr(value, 'tolist'):
                            rect[key] = value.tolist()
                        elif hasattr(value, 'item'):
                            rect[key] = value.item()
                
                result = {
                    'config': config,
                    'rectangles_found': len(rectangles),
                    'rectangles': rectangles,
                    'processing_time': processing_time,
                    'seuil_reduit': custom_params['min_area'],
                    'seuil_original': page_analysis['detection_params']['min_area'],
                    'image_info': {
                        'size': f"{page_cv.shape[1]}×{page_cv.shape[0]}",
                        'megapixels': round((page_cv.shape[0] * page_cv.shape[1]) / 1000000, 1)
                    }
                }
                
                results.append(result)
                logger.info(f"   ✅ Résultat: {len(rectangles)} rectangles trouvés")
                
            except Exception as e:
                logger.error(f"   ❌ Erreur config {config}: {e}")
                continue
        
        # Trier par nombre de rectangles trouvés (décroissant)
        results.sort(key=lambda x: x['rectangles_found'], reverse=True)
        
        logger.info(f"📊 RÉSUMÉ TESTS:")
        for i, result in enumerate(results[:3]):  # Top 3
            config = result['config']
            logger.info(f"   {i+1}. {result['rectangles_found']} rectangles → Mode={config['mode']}, Sens={config['sensitivity']}")
        
        return jsonify({
            'success': True,
            'page_number': page_number,
            'filename': filename,
            'total_configs_tested': len(results),
            'best_result': results[0] if results else None,
            'all_results': results,
            'recommendations': {
                'best_config': results[0]['config'] if results else None,
                'max_rectangles_found': results[0]['rectangles_found'] if results else 0,
                'problem_analysis': 'Seuil aire trop élevé' if results and results[0]['rectangles_found'] > 1 else 'Problème détection de bords'
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur debug rectangles manqués: {str(e)}")
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

@app.route('/emergency_reprocess/<filename>')
def emergency_reprocess_pdf(filename):
    """Endpoint d'urgence pour retraiter un PDF avec paramètres optimisés"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        logger.info(f"🚨 RETRAITEMENT D'URGENCE - {filename}")
        
        # **PARAMÈTRES OPTIMISÉS BASÉS SUR LES TESTS**
        # Utiliser les paramètres qui fonctionnent en debug
        sensitivity = 30  # Plus sensible
        mode = 'documents'  # Mode optimal pour Picasso
        
        # Compter les pages
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
        except Exception as e:
            total_pages = 196  # Valeur connue pour Picasso
        
        logger.info(f"🔄 Retraitement avec paramètres optimisés: mode={mode}, sensibilité={sensitivity}")
        
        # **NETTOYER LES DONNÉES PRÉCÉDENTES**
        pdf_processor.clear()
        pdf_processor.pages = []
        pdf_processor.pdf_rectangles = []
        pdf_processor.original_filename = filename.replace('.pdf', '').replace('.ocr', '')
        
        # **TRAITEMENT PAGE PAR PAGE AVEC PARAMÈTRES OPTIMISÉS**
        total_rectangles = 0
        pages_processed = 0
        
        for page_num in range(1, min(total_pages + 1, 50)):  # Limiter à 50 pages pour test
            try:
                logger.info(f"📄 Retraitement page {page_num}/{min(total_pages, 50)}...")
                
                # Analyser la page
                page_analysis = page_analyzer.analyze_page_dimensions(filepath, page_num)
                
                # **FORCER PARAMÈTRES MOINS STRICTS**
                custom_params = page_analysis['detection_params'].copy()
                custom_params['min_area'] = custom_params['min_area'] // 3  # Diviser par 3 au lieu de 4
                custom_params['max_rectangles'] = 15  # Plus de rectangles
                
                # Convertir la page avec DPI adaptatif
                optimal_dpi = page_analysis['recommended_dpi']
                page_images = convert_from_path(
                    filepath, 
                    dpi=optimal_dpi,
                    first_page=page_num,
                    last_page=page_num
                )
                
                if not page_images:
                    continue
                    
                page_image = page_images[0]
                page_array = np.array(page_image)
                page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
                
                # Stocker l'image
                page_data = {
                    'page_number': page_num,
                    'image': page_cv
                }
                pdf_processor.pages.append(page_data)
                
                # Détecter avec paramètres optimisés
                rectangles = detector.detect_rectangles(
                    page_cv, 
                    sensitivity, 
                    mode,
                    adaptive_params=custom_params,
                    debug_page_num=page_num
                )
                
                # Convertir pour JSON
                for rect in rectangles:
                    if 'corners' in rect and hasattr(rect['corners'], 'tolist'):
                        rect['corners'] = rect['corners'].tolist()
                    if 'bbox' in rect and isinstance(rect['bbox'], tuple):
                        x, y, w, h = rect['bbox']
                        rect['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                    if 'contour' in rect:
                        del rect['contour']
                    for key, value in rect.items():
                        if hasattr(value, 'tolist'):
                            rect[key] = value.tolist()
                        elif hasattr(value, 'item'):
                            rect[key] = value.item()
                
                # Stocker les résultats
                page_result = {
                    'page_number': page_num,
                    'rectangles': rectangles,
                    'rectangles_count': len(rectangles)
                }
                pdf_processor.pdf_rectangles.append(page_result)
                
                total_rectangles += len(rectangles)
                pages_processed += 1
                
                logger.info(f"✅ Page {page_num}: {len(rectangles)} rectangles détectés")
                
                # Garder seulement les 5 dernières pages en mémoire
                if len(pdf_processor.pages) > 5:
                    pdf_processor.pages.pop(0)
                
            except Exception as e:
                logger.error(f"❌ Erreur page {page_num}: {e}")
                continue
        
        # **MISE À JOUR DES RÉSULTATS GLOBAUX**
        pdf_processor.current_result = {
            'success': True,
            'total_pages': pages_processed,
            'total_rectangles': total_rectangles,
            'pages': pdf_processor.pdf_rectangles,
            'filename': pdf_processor.original_filename,
            'is_pdf': True,
            'emergency_reprocess': True
        }
        pdf_processor.processing_in_progress = False
        
        logger.info(f"🎉 Retraitement terminé: {pages_processed} pages, {total_rectangles} rectangles")
        
        return jsonify({
            'success': True,
            'message': f'Retraitement terminé avec paramètres optimisés',
            'pages_processed': pages_processed,
            'total_rectangles': total_rectangles,
            'filename': filename,
            'download_ready': total_rectangles > 0,
            'optimizations_applied': {
                'mode': mode,
                'sensitivity': sensitivity,
                'seuil_reduit': 'Divisé par 3',
                'dpi': 'Adaptatif par page'
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur retraitement d'urgence: {str(e)}")
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

class PDFPageAnalyzer:
    """Analyseur intelligent de pages PDF pour adapter automatiquement les paramètres"""
    
    def __init__(self):
        self.page_cache = {}  # Cache des analyses de pages
    
    def analyze_page_dimensions(self, pdf_path, page_number):
        """
        Analyse les dimensions physiques d'une page PDF spécifique
        Retourne: {width_mm, height_mm, area_mm2, page_format, recommended_dpi}
        """
        cache_key = f"{pdf_path}_{page_number}"
        if cache_key in self.page_cache:
            return self.page_cache[cache_key]
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                if page_number > len(pdf_reader.pages):
                    raise Exception(f"Page {page_number} n'existe pas")
                
                page = pdf_reader.pages[page_number - 1]  # PyPDF2 est 0-indexé
                
                # Récupérer les dimensions en points (1 point = 1/72 pouce)
                mediabox = page.mediabox
                width_points = float(mediabox.width)
                height_points = float(mediabox.height)
                
                # Convertir en millimètres (1 pouce = 25.4 mm)
                width_mm = width_points * 25.4 / 72
                height_mm = height_points * 25.4 / 72
                area_mm2 = width_mm * height_mm
                
                # Identifier le format de page
                page_format = self._identify_page_format(width_mm, height_mm)
                
                # Recommander un DPI adapté
                recommended_dpi = self._calculate_optimal_dpi(width_mm, height_mm, area_mm2)
                
                # Calculer les paramètres de détection optimaux
                detection_params = self._calculate_detection_params(width_mm, height_mm, recommended_dpi)
                
                analysis = {
                    'width_mm': round(width_mm, 1),
                    'height_mm': round(height_mm, 1),
                    'area_mm2': round(area_mm2, 0),
                    'page_format': page_format,
                    'recommended_dpi': recommended_dpi,
                    'detection_params': detection_params
                }
                
                # Mettre en cache
                self.page_cache[cache_key] = analysis
                
                logger.info(f"📏 Page {page_number}: {width_mm:.1f}×{height_mm:.1f}mm ({page_format}) → DPI {recommended_dpi}")
                
                return analysis
                
        except Exception as e:
            logger.error(f"❌ Erreur analyse page {page_number}: {e}")
            # Valeurs par défaut pour A4
            return {
                'width_mm': 210.0,
                'height_mm': 297.0,
                'area_mm2': 62370,
                'page_format': 'A4 (par défaut)',
                'recommended_dpi': 300,
                'detection_params': self._calculate_detection_params(210, 297, 300)
            }
    
    def _identify_page_format(self, width_mm, height_mm):
        """Identifie le format de page basé sur les dimensions"""
        # Normaliser pour orientation portrait
        w, h = sorted([width_mm, height_mm])
        
        formats = {
            (105, 148): "A6",
            (148, 210): "A5", 
            (210, 297): "A4",
            (297, 420): "A3",
            (420, 594): "A2",
            (594, 841): "A1",
            (216, 279): "Letter US",
            (216, 356): "Legal US",
            (432, 279): "Tabloid",
        }
        
        # Trouver le format le plus proche (tolérance 5mm)
        for (fw, fh), format_name in formats.items():
            if abs(w - fw) <= 5 and abs(h - fh) <= 5:
                return format_name
        
        # Format personnalisé
        return f"Personnalisé {w:.0f}×{h:.0f}mm"
    
    def _calculate_optimal_dpi(self, width_mm, height_mm, area_mm2):
        """Calcule le DPI optimal basé sur la taille de page"""
        # Stratégie : maintenir une résolution cible d'environ 50-100 mégapixels max
        target_megapixels = 75  # Objectif : 75 MP par page
        
        # Calculer le DPI pour atteindre la cible
        width_inches = width_mm / 25.4
        height_inches = height_mm / 25.4
        
        # DPI pour atteindre le target de mégapixels
        optimal_dpi = int((target_megapixels * 1000000) ** 0.5 / max(width_inches, height_inches))
        
        # Contraintes intelligentes
        if area_mm2 < 30000:  # Petite page (< A5)
            dpi = min(600, max(optimal_dpi, 400))  # DPI élevé pour petites pages
        elif area_mm2 < 70000:  # Page normale (A5-A4)
            dpi = min(500, max(optimal_dpi, 300))  # DPI équilibré
        elif area_mm2 < 150000:  # Grande page (A4-A3)
            dpi = min(400, max(optimal_dpi, 200))  # DPI réduit pour grandes pages
        else:  # Très grande page (> A3)
            dpi = min(300, max(optimal_dpi, 150))  # DPI faible pour très grandes pages
        
        # S'assurer que c'est un multiple de 50 pour l'efficacité
        dpi = round(dpi / 50) * 50
        
        return max(150, min(600, dpi))  # Entre 150 et 600 DPI
    
    def _calculate_detection_params(self, width_mm, height_mm, dpi):
        """Calcule les paramètres de détection optimaux"""
        # Calculer la résolution finale
        width_pixels = int(width_mm * dpi / 25.4)
        height_pixels = int(height_mm * dpi / 25.4)
        total_pixels = width_pixels * height_pixels
        
        # Adapter les seuils selon la résolution réelle
        if total_pixels > 80_000_000:  # > 80 MP
            min_area_divisor = 800  # Seuil très strict
            max_rectangles = 60
        elif total_pixels > 50_000_000:  # 50-80 MP
            min_area_divisor = 600  # Seuil strict
            max_rectangles = 50
        elif total_pixels > 20_000_000:  # 20-50 MP
            min_area_divisor = 400  # Seuil équilibré
            max_rectangles = 40
        else:  # < 20 MP
            min_area_divisor = 200  # Seuil permissif
            max_rectangles = 30
        
        return {
            'estimated_pixels': total_pixels,
            'estimated_megapixels': round(total_pixels / 1_000_000, 1),
            'min_area_divisor': min_area_divisor,
            'max_rectangles': max_rectangles,
            'min_area': total_pixels // min_area_divisor
        }

# Instanciation des analyseurs après définition des classes
page_analyzer = PDFPageAnalyzer()

if __name__ == '__main__':
    print("🚀 Backend de détection automatique de rectangles")
    print("📡 API disponible sur http://localhost:5000")
    print("🔗 WebSockets activés pour suivi en temps réel")
    print("")
    print("🤖 MODE AUTOMATIQUE COMPLET:")
    print("   POST /upload_auto - Fait TOUT automatiquement!")
    print("")
    print("✨ Ce qui se passe automatiquement:")
    print("   1. 🎯 Détection intelligente (teste plusieurs configs)")
    print("   2. 🖼️  Extraction automatique des images")  
    print("   3. 💾 Sauvegarde en temps réel dans un dossier")
    print("   4. 📊 Logs JSON détaillés par page")
    print("   5. 🏷️  Organisation avec/sans numéros d'œuvre")
    print("   6. 🖼️  Miniatures pour aperçu rapide")
    print("   7. 📋 Résumé HTML avec galerie")
    print("   8. 📁 Ouverture automatique du dossier")
    print("")
    print("📁 Structure générée automatiquement:")
    print("   extractions/nom_document_YYYYMMDD_HHMMSS/")
    print("   ├── avec_numeros/     # Images avec n° d'œuvre")
    print("   ├── sans_numeros/     # Images sans n°")
    print("   ├── miniatures/       # Aperçus 200px")
    print("   ├── page_XXX_log.json # Log détaillé par page")
    print("   ├── complete_log.json # Log complet")
    print("   ├── info.txt          # Résumé texte")
    print("   └── resume.html       # Galerie interactive")
    print("")
    print("🔍 Logs JSON contiennent:")
    print("   • Config utilisée par page")
    print("   • Rectangles trouvés + détails")
    print("   • Temps de traitement")
    print("   • Images sauvées")
    print("   • Erreurs éventuelles")
    print("")
    print("🎉 Plus besoin de paramètres - C'est AUTOMATIQUE!")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 