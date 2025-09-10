"""
Collection Picasso - Configuration spécifique pour les catalogues Picasso
"""

from typing import List, Dict, Tuple
import numpy as np
import cv2
from .base_collection import ArtworkCollection


class PicassoCollection(ArtworkCollection):
    """
    Collection Pablo Picasso
    - Numéros généralement sous l'œuvre
    - Sommaires disponibles
    - Numéros courts (1-4 chiffres principalement)
    """
    
    def __init__(self):
        super().__init__(
            name="Picasso",
            description="Pablo Picasso - Numéros sous les œuvres, avec sommaires"
        )
    
    def get_detection_zones(self, image: np.ndarray, rectangle: dict) -> List[Tuple[int, int, int, int]]:
        """
        Zones de détection optimisées pour Picasso
        Priorité aux zones sous l'image
        """
        H, W = image.shape[:2]
        bbox = rectangle.get('bbox', {})
        x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)

        # Fonction pour limiter les zones aux bords de l'image
        def clamp_zone(zx, zy, zw, zh):
            zx = max(0, zx)
            zy = max(0, zy)
            zw = max(0, min(zw, W - zx))
            zh = max(0, min(zh, H - zy))
            return (zx, zy, zw, zh)

        # Zones de recherche par priorité pour Picasso
        pad_x = max(10, w // 20)
        pad_y = max(10, h // 20)

        zones = [
            # PRIORITÉ 1: Petite bande sous l'image (30-80px) - Zone principale pour Picasso
            clamp_zone(x - pad_x, y + h + 2, w + 2 * pad_x, max(30, min(80, h // 3))),
            
            # PRIORITÉ 2: Bande plus large sous l'image (40-100px)
            clamp_zone(x - pad_x*2, y + h + 2, w + 4 * pad_x, max(40, min(100, h // 2))),
            
            # PRIORITÉ 3: Très fine bande DANS l'image - bas (20px)
            clamp_zone(x + w//6, y + h - 20, w*2//3, 20),
            
            # PRIORITÉ 4: Très fine bande DANS l'image - haut (20px)
            clamp_zone(x + w//6, y, w*2//3, 20),
            
            # PRIORITÉ 5: Zone à droite de l'image
            clamp_zone(x + w + 4, y, min(80 + w // 3, W - (x + w + 4)), min(h, 120)),
            
            # PRIORITÉ 6: Zone à gauche de l'image
            clamp_zone(max(0, x - (60 + w // 3)), y, min(80 + w // 3, x), min(h, 120)),
        ]
        
        return zones
    
    def get_number_validation_rules(self) -> Dict:
        """
        Règles de validation pour les numéros Picasso
        """
        return {
            'min_length': 1,
            'max_length': 6,
            'preferred_length_range': (1, 4),  # Picasso a souvent des numéros courts
            'exclude_years': True,
            'exclude_patterns': [r'19\d{2}', r'20\d{2}'],  # Exclure les années
            'allow_leading_zeros': False
        }
    
    def get_ocr_config(self) -> Dict:
        """
        Configuration OCR optimisée pour Picasso
        """
        return {
            'psm_configs': [
                '--psm 7 -c tessedit_char_whitelist=0123456789',  # Ligne unique, chiffres seulement
                '--psm 8 -c tessedit_char_whitelist=0123456789',  # Mot unique, chiffres seulement
                '--psm 6 -c tessedit_char_whitelist=0123456789',  # Bloc uniforme
            ],
            'scale_factor': 3.0,
            'preprocessing': [
                'otsu',
                'otsu_inv',
                'adaptive',
                'clahe_otsu'
            ]
        }
    
    def get_scoring_weights(self) -> Dict:
        """
        Poids de scoring spécifiques à Picasso
        """
        return {
            'zone_weights': [4.0, 3.5, 3.0, 2.5, 1.5, 1.5],  # Forte priorité aux zones sous l'image
            'length_bonus': {1: 2.0, 2: 2.0, 3: 2.0, 4: 1.5, 5: 1.0, 6: 0.8},  # Bonus pour numéros courts
            'proximity_bonus': 1.2,
            'early_stop_threshold': 8.0  # Arrêt précoce si très bon score
        }
    
    def has_summary_page(self) -> bool:
        """
        Picasso a généralement des pages de sommaire
        """
        return True
    
    def get_summary_detection_config(self) -> Dict:
        """
        Configuration pour détecter les sommaires Picasso
        """
        return {
            'enabled': True,
            'keywords': ['sommaire', 'table des matières', 'contents', 'index', 'planches'],
            'min_entries': 5,
            'number_pattern': r'\b\d{1,4}\b',  # Numéros courts typiques
            'page_indicators': ['p.', 'page', 'pl.', 'planche']
        }
