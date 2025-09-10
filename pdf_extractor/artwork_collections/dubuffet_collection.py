"""
Collection Dubuffet - Configuration spécifique pour les catalogues Jean Dubuffet
"""

from typing import List, Dict, Tuple
import numpy as np
import cv2
from .base_collection import ArtworkCollection


class DubuffetCollection(ArtworkCollection):
    """
    Collection Jean Dubuffet
    - Numéros directement sous l'œuvre (pas de sommaire séparé)
    - Numéros souvent plus proches de l'image
    - Peut avoir des numéros plus variés
    """
    
    def __init__(self):
        super().__init__(
            name="Dubuffet",
            description="Jean Dubuffet - Numéros directement sous les œuvres, pas de sommaire"
        )
    
    def get_detection_zones(self, image: np.ndarray, rectangle: dict) -> List[Tuple[int, int, int, int]]:
        """
        Zones de détection optimisées pour Dubuffet
        Focus sur les zones très proches de l'image car pas de sommaire séparé
        """
        H, W = image.shape[:2]
        bbox = rectangle.get('bbox', {})
        x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)

        def clamp_zone(zx, zy, zw, zh):
            zx = max(0, zx)
            zy = max(0, zy)
            zw = max(0, min(zw, W - zx))
            zh = max(0, min(zh, H - zy))
            return (zx, zy, zw, zh)

        # Zones spécifiques à Dubuffet - plus proches de l'image
        pad_x = max(8, w // 25)  # Padding plus petit
        pad_y = max(8, h // 25)

        zones = [
            # PRIORITÉ 1: Zone très proche sous l'image (20-50px) - Plus proche que Picasso
            clamp_zone(x - pad_x//2, y + h + 1, w + pad_x, max(20, min(50, h // 4))),
            
            # PRIORITÉ 2: Bande fine DANS l'image - bas (25px) - Plus importante que pour Picasso
            clamp_zone(x + w//8, y + h - 25, w*3//4, 25),
            
            # PRIORITÉ 3: Zone immédiatement sous l'image, centrée
            clamp_zone(x + w//6, y + h + 1, w*2//3, max(25, min(60, h // 3))),
            
            # PRIORITÉ 4: Zone à droite, plus proche
            clamp_zone(x + w + 2, y + h//4, min(60, W - (x + w + 2)), min(h//2, 80)),
            
            # PRIORITÉ 5: Zone à gauche, plus proche  
            clamp_zone(max(0, x - 60), y + h//4, min(60, x), min(h//2, 80)),
            
            # PRIORITÉ 6: Bande plus large sous l'image (fallback)
            clamp_zone(x - pad_x, y + h + 2, w + 2 * pad_x, max(30, min(70, h // 2))),
        ]
        
        return zones
    
    def get_number_validation_rules(self) -> Dict:
        """
        Règles de validation pour les numéros Dubuffet
        """
        return {
            'min_length': 1,
            'max_length': 6,
            'preferred_length_range': (1, 5),  # Dubuffet peut avoir des numéros un peu plus longs
            'exclude_years': True,
            'exclude_patterns': [r'19\d{2}', r'20\d{2}'],
            'allow_leading_zeros': True,  # Dubuffet peut avoir des numéros avec zéros
            'allow_alpha_suffix': False  # Pas de lettres pour l'instant
        }
    
    def get_ocr_config(self) -> Dict:
        """
        Configuration OCR optimisée pour Dubuffet
        """
        return {
            'psm_configs': [
                '--psm 7 -c tessedit_char_whitelist=0123456789',
                '--psm 8 -c tessedit_char_whitelist=0123456789',
                '--psm 6 -c tessedit_char_whitelist=0123456789',
                '--psm 13 -c tessedit_char_whitelist=0123456789',  # Ligne brute - utile si numéros isolés
            ],
            'scale_factor': 3.5,  # Légèrement plus élevé pour capturer les détails
            'preprocessing': [
                'otsu',
                'otsu_inv', 
                'adaptive',
                'clahe_otsu',
                'gaussian_blur_otsu'  # Ajout d'un préprocessing supplémentaire
            ]
        }
    
    def get_scoring_weights(self) -> Dict:
        """
        Poids de scoring spécifiques à Dubuffet
        """
        return {
            'zone_weights': [4.5, 4.0, 3.5, 2.0, 2.0, 1.5],  # Priorité très forte aux zones proches
            'length_bonus': {1: 2.0, 2: 2.0, 3: 1.8, 4: 1.5, 5: 1.2, 6: 1.0},
            'proximity_bonus': 1.5,  # Bonus plus élevé pour la proximité
            'early_stop_threshold': 9.0  # Seuil plus élevé car on cherche la précision
        }
    
    def has_summary_page(self) -> bool:
        """
        Dubuffet n'a généralement PAS de pages de sommaire séparées
        """
        return False
    
    def get_summary_detection_config(self) -> Dict:
        """
        Configuration pour Dubuffet (pas de sommaire)
        """
        return {
            'enabled': False,
            'keywords': [],
            'min_entries': 0,
            'number_pattern': r'\b\d{1,5}\b',
            'page_indicators': []
        }
    
    def preprocess_number(self, number_str: str) -> str:
        """
        Préprocessing spécifique pour Dubuffet
        """
        if not number_str:
            return None
            
        # Nettoyer les caractères parasites
        cleaned = ''.join(c for c in number_str if c.isdigit())
        
        if not cleaned:
            return None
            
        # Appliquer les règles de base
        result = super().preprocess_number(cleaned)
        
        return result
