"""
Utilitaires pour le traitement d'images
"""
import cv2
import numpy as np
from typing import Tuple, Optional
from config import DETECTION_CONFIG

class ImageUtils:
    """Utilitaires pour le traitement d'images"""
    
    @staticmethod
    def create_thumbnail(image: np.ndarray, max_size: int = None) -> np.ndarray:
        """Crée une miniature de l'image"""
        if max_size is None:
            max_size = DETECTION_CONFIG['thumbnail_size']
            
        height, width = image.shape[:2]
        
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    @staticmethod
    def resize_for_ocr(image: np.ndarray, scale_factor: float = 3.0) -> np.ndarray:
        """Redimensionne l'image pour améliorer l'OCR"""
        return cv2.resize(image, None, fx=scale_factor, fy=scale_factor, 
                         interpolation=cv2.INTER_CUBIC)
    
    @staticmethod
    def is_image_valid(image: np.ndarray) -> bool:
        """Vérifie si l'image est valide"""
        if image is None:
            return False
        
        height, width = image.shape[:2]
        min_size = DETECTION_CONFIG['min_image_size']
        
        return height >= min_size[0] and width >= min_size[1]
    
    @staticmethod
    def clamp_zone(x: int, y: int, w: int, h: int, 
                  max_width: int, max_height: int) -> Tuple[int, int, int, int]:
        """Clamp une zone aux limites de l'image"""
        x = max(0, x)
        y = max(0, y)
        w = max(0, min(w, max_width - x))
        h = max(0, min(h, max_height - y))
        return x, y, w, h
    
    @staticmethod
    def calculate_aspect_ratio(width: int, height: int) -> float:
        """Calcule le ratio d'aspect"""
        if height == 0:
            return float('inf')
        return width / height
    
    @staticmethod
    def is_rectangle_valid(bbox: dict, min_area: float = 100) -> bool:
        """Vérifie si un rectangle est valide"""
        w, h = bbox.get('w', 0), bbox.get('h', 0)
        area = w * h
        
        if area < min_area:
            return False
        
        aspect_ratio = ImageUtils.calculate_aspect_ratio(w, h)
        return 0.1 < aspect_ratio < 10  # Ratio raisonnable
