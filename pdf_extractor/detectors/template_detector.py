"""
Détecteur basé sur le template matching
"""
import cv2
import numpy as np
from typing import List, Dict, Any
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from detectors.base_detector import BaseDetector

class TemplateDetector(BaseDetector):
    """Détecteur basé sur des templates de formes communes"""
    
    def __init__(self):
        super().__init__("template_detector")
    
    def detect(self, image: np.ndarray, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Détecte les rectangles en utilisant le template matching"""
        rectangles = []
        
        try:
            # Créer des templates simples pour différentes tailles
            templates = self._create_templates()
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            for template_name, template in templates:
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= 0.3)  # Seuil permissif
                
                for pt in zip(*locations[::-1]):
                    x, y = pt
                    w, h = template.shape[1], template.shape[0]
                    
                    rectangles.append(self._create_rectangle(
                        np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]),
                        {'x': x, 'y': y, 'w': w, 'h': h},
                        w * h,
                        float(result[y//template.shape[0], x//template.shape[1]]) 
                        if y//template.shape[0] < result.shape[0] and x//template.shape[1] < result.shape[1] 
                        else 0.3,
                        f'template_{template_name}'
                    ))
        
        except Exception as e:
            self.logger.debug(f"Template detection error: {e}")
        
        return rectangles[:10]  # Limiter pour éviter trop de faux positifs
    
    def _create_templates(self) -> List[tuple]:
        """Crée des templates de différentes tailles"""
        templates = []
        
        # Templates rectangulaires de différentes tailles
        for w, h in [(100, 150), (150, 200), (200, 250), (80, 120), (60, 80)]:
            template = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(template, (5, 5), (w-5, h-5), 255, 2)
            templates.append(('rect', template))
        
        return templates
