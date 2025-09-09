"""
Détecteur ultra sensible pour les rectangles
"""
import cv2
import numpy as np
from typing import List, Dict, Any
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from detectors.base_detector import BaseDetector
from config import DETECTION_CONFIG

class UltraDetector(BaseDetector):
    """Détecteur ultra sensible utilisant plusieurs configurations"""
    
    def __init__(self):
        super().__init__("ultra_detector")
    
    def detect(self, image: np.ndarray, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Détecte les rectangles avec plusieurs configurations ultra sensibles"""
        height, width = image.shape[:2]
        total_pixels = height * width
        
        all_rectangles = []
        
        # Tester toutes les configurations ultra sensibles
        for config_item in DETECTION_CONFIG['ultra_configs']:
            self.logger.debug(f"    🧪 Test config: {config_item['name']}")
            rectangles = self._detect_with_config(image, config_item, total_pixels)
            
            self.logger.debug(f"      → {len(rectangles)} rectangles trouvés")
            
            # Ajouter tous les rectangles uniques
            for rect in rectangles:
                if not self._is_duplicate_rectangle(rect, all_rectangles):
                    all_rectangles.append(rect)
        
        return all_rectangles
    
    def _detect_with_config(self, image: np.ndarray, config: Dict[str, Any], 
                           total_pixels: int) -> List[Dict[str, Any]]:
        """Détecte avec une configuration spécifique"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        sensitivity = config['sensitivity']
        mode = config['mode']
        min_area_div = config['min_area_div']
        
        # Prétraitement selon le mode
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
        
        # Détection de bords multi-méthodes
        edges1 = cv2.Canny(enhanced, canny_low, canny_high)
        edges2 = cv2.Canny(enhanced, max(1, canny_low//2), max(3, canny_high//2))
        
        # Gradient morphologique
        kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gradient = cv2.morphologyEx(enhanced, cv2.MORPH_GRADIENT, kernel_grad)
        _, edges3 = cv2.threshold(gradient, sensitivity // 10, 255, cv2.THRESH_BINARY)
        
        # Seuillage adaptatif
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
            
            # Vérifier que le contour n'est pas trop déformé
            bbox = cv2.boundingRect(contour)
            bbox_area = bbox[2] * bbox[3]
            area_ratio = area / bbox_area if bbox_area > 0 else 0
            
            if area_ratio < 0.4:
                continue
            
            # Approximation très permissive
            epsilon_values = [0.001, 0.002, 0.005, 0.01, 0.02, 0.03]
            
            for epsilon_mult in epsilon_values:
                epsilon = epsilon_mult * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    x, y, w, h = cv2.boundingRect(contour)
                    rectangles.append(self._create_rectangle(
                        approx.reshape(4, 2),
                        {'x': x, 'y': y, 'w': w, 'h': h},
                        area,
                        0.7,
                        f'ultra_{mode}'
                    ))
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
                    
                    rectangles.append(self._create_rectangle(
                        corners,
                        {'x': x, 'y': y, 'w': w, 'h': h},
                        area,
                        area_ratio,
                        f'ultra_bbox_{mode}'
                    ))
            
            # Limite généreuse
            if len(rectangles) >= DETECTION_CONFIG['max_rectangles_per_config']:
                break
        
        return rectangles
