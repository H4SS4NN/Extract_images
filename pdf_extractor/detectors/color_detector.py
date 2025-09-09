"""
Détecteur basé sur l'analyse des couleurs et contrastes
"""
import cv2
import numpy as np
from typing import List, Dict, Any
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from detectors.base_detector import BaseDetector

class ColorDetector(BaseDetector):
    """Détecteur basé sur l'analyse des couleurs et contrastes"""
    
    def __init__(self):
        super().__init__("color_detector")
    
    def detect(self, image: np.ndarray, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Détecte les rectangles basés sur l'analyse de couleur"""
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
                    rectangles.append(self._create_rectangle(
                        np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                        {'x': x, 'y': y, 'w': w, 'h': h},
                        area,
                        min(1.0, area / min_area / 10),
                        'color_analysis'
                    ))
        
        except Exception as e:
            self.logger.debug(f"Color detection error: {e}")
        
        return rectangles
