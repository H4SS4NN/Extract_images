"""
Classe de base pour tous les détecteurs
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np
from utils import logger

class BaseDetector(ABC):
    """Classe de base pour tous les détecteurs de rectangles"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logger
    
    @abstractmethod
    def detect(self, image: np.ndarray, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Détecte les rectangles dans l'image
        
        Args:
            image: Image OpenCV (BGR)
            config: Configuration spécifique au détecteur
            
        Returns:
            Liste de dictionnaires contenant les rectangles détectés
        """
        pass
    
    def _create_rectangle(self, corners: np.ndarray, bbox: Dict[str, int], 
                         area: float, confidence: float = 0.5, 
                         method: str = None) -> Dict[str, Any]:
        """Crée un dictionnaire de rectangle standardisé"""
        return {
            'id': 0,  # Sera assigné par le gestionnaire
            'corners': corners,
            'bbox': bbox,
            'area': area,
            'method': method or self.name,
            'confidence': confidence,
            'detector': self.name
        }
    
    def _is_duplicate_rectangle(self, new_rect: Dict[str, Any], 
                               existing_rects: List[Dict[str, Any]], 
                               threshold: float = 0.7) -> bool:
        """Vérifie si un rectangle est un doublon"""
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
                if overlap_ratio > threshold:
                    return True
        
        return False
