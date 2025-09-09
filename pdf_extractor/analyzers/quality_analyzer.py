"""
Analyseur de qualité des images extraites
"""
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from utils import logger

class QualityAnalyzer:
    """Analyse la qualité et la validité des images extraites"""
    
    def __init__(self):
        self.logger = logger
    
    def analyze_image_quality(self, image: np.ndarray, 
                            all_images_in_page: List[np.ndarray]) -> Dict[str, Any]:
        """Analyse si une image est douteuse"""
        reasons = []
        confidence = 1.0
        
        height, width = image.shape[:2]
        
        # 1. Vérifier les dimensions suspectes
        if all_images_in_page:
            # Calculer les statistiques de taille de la page
            sizes = [(img.shape[0] * img.shape[1]) for img in all_images_in_page]
            mean_size = np.mean(sizes)
            std_size = np.std(sizes)
            current_size = height * width
            
            # Si beaucoup plus petit que la moyenne
            if current_size < mean_size - 2 * std_size:
                reasons.append("taille_anormale")
                confidence *= 0.5
        
        # 2. Vérifier si c'est principalement blanc/vide
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        white_pixels = np.sum(gray > 240) / gray.size
        
        if white_pixels > 0.95:
            reasons.append("image_vide")
            confidence *= 0.2
        
        # 3. Vérifier le ratio d'aspect
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 8:  # Très allongé
            reasons.append("ratio_extreme")
            confidence *= 0.6
        
        # 4. Vérifier la variance (image uniforme)
        variance = np.var(gray)
        if variance < 100:
            reasons.append("peu_de_contenu")
            confidence *= 0.4
        
        # 5. Détection de contours
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        
        if edge_ratio < 0.01:
            reasons.append("pas_de_contours")
            confidence *= 0.3
        
        is_doubtful = confidence < 0.7 or len(reasons) > 1
        
        return {
            'is_doubtful': is_doubtful,
            'confidence': confidence,
            'reasons': reasons
        }
    
    def get_quality_description(self, reason: str) -> str:
        """Retourne une description lisible d'une raison de qualité"""
        descriptions = {
            'taille_anormale': '• Taille anormalement petite par rapport aux autres images',
            'image_vide': '• Image principalement blanche/vide (>95% pixels clairs)',
            'ratio_extreme': '• Ratio d\'aspect extrême (trop allongée)',
            'peu_de_contenu': '• Peu de contenu visuel détecté (faible variance)',
            'pas_de_contours': '• Aucun contour significatif détecté'
        }
        return descriptions.get(reason, f'• {reason}')
