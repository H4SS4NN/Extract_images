#!/usr/bin/env python3
"""
Collection Picasso - Gestion des œuvres de Pablo Picasso.
Utilise le système de sommaire multi-pages existant.
"""

import logging
import cv2
import numpy as np
from typing import Dict, Optional, List, Tuple
from .base_collection import BaseCollection

logger = logging.getLogger(__name__)


class PicassoCollection(BaseCollection):
    """
    Collection pour les œuvres de Pablo Picasso.
    Utilise le système de sommaire multi-pages et la détection avancée.
    """
    
    def __init__(self):
        super().__init__(
            name="picasso",
            description="Collection Picasso avec sommaire multi-pages en fin de PDF"
        )
        self.logger = logging.getLogger(f"{__name__}.picasso")
    
    def extract_toc(self, pdf_path: str) -> Optional[Dict]:
        """
        Extrait le sommaire multi-pages du PDF Picasso.
        
        Args:
            pdf_path: Chemin vers le PDF
            
        Returns:
            Dictionnaire contenant les données du sommaire ou None
        """
        try:
            import sys
            from pathlib import Path
            # Ajouter le répertoire parent au path pour les imports
            sys.path.append(str(Path(__file__).parent.parent))
            from toc_planches import extract_toc_from_pdf_multipage
            
            self.logger.info("🔍 Extraction du sommaire Picasso (multi-pages)...")
            toc_data = extract_toc_from_pdf_multipage(pdf_path, last_n=15)
            
            if toc_data:
                self.logger.info(f"📋 {len(toc_data.get('plates', []))} planches mappées")
                return toc_data
            else:
                self.logger.warning("⚠️ Aucun sommaire trouvé")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'extraction du sommaire: {e}")
            return None
    
    def detect_artwork_number(self, image, rectangle: Dict, page_context: Dict) -> Optional[str]:
        """
        Détecte le numéro d'œuvre dans une image Picasso.
        Utilise la méthode de détection avancée existante.
        
        Args:
            image: Image extraite (numpy array)
            rectangle: Dictionnaire contenant les coordonnées du rectangle
            page_context: Contexte de la page
            
        Returns:
            Numéro d'œuvre détecté (string) ou None si non trouvé
        """
        try:
            # Utiliser la méthode de détection existante
            return self._detect_artwork_number_picasso(image, rectangle)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la détection du numéro: {e}")
            return None
    
    def _detect_artwork_number_picasso(self, image: np.ndarray, rectangle: Dict) -> Optional[str]:
        """
        Méthode de détection spécifique à Picasso.
        Utilise les zones de recherche optimisées.
        
        Args:
            image: Image extraite
            rectangle: Coordonnées du rectangle
            
        Returns:
            Numéro détecté ou None
        """
        try:
            import pytesseract
            import re
            
            # Vérifier la disponibilité de Tesseract
            try:
                _ = pytesseract.get_tesseract_version()
            except Exception:
                self.logger.warning("⚠️ Tesseract non disponible")
                return None
            
            # Extraire les coordonnées
            x, y, w, h = rectangle['x'], rectangle['y'], rectangle['w'], rectangle['h']
            
            # Définir les zones de recherche avec priorité stricte
            search_zones = self._get_picasso_search_zones(x, y, w, h, image.shape)
            
            # Tester chaque zone dans l'ordre de priorité
            for zone_name, (zone_x, zone_y, zone_w, zone_h) in search_zones.items():
                if zone_w <= 0 or zone_h <= 0:
                    continue
                
                # Extraire la zone
                zone = image[zone_y:zone_y+zone_h, zone_x:zone_x+zone_w]
                
                if zone.size == 0:
                    continue
                
                # OCR optimisé pour les numéros courts
                config = "--psm 7 -c tessedit_char_whitelist=0123456789"
                text = pytesseract.image_to_string(zone, config=config)
                
                # Chercher un numéro de 1-6 chiffres
                match = re.search(r"\b\d{1,6}\b", text)
                if match:
                    number = match.group()
                    self.logger.debug(f"🔍 Numéro détecté dans {zone_name}: {number}")
                    return number
            
            self.logger.debug("🔍 Aucun numéro détecté dans les zones de recherche")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la détection Picasso: {e}")
            return None
    
    def _get_picasso_search_zones(self, x: int, y: int, w: int, h: int, 
                                 image_shape: Tuple[int, int, int]) -> Dict[str, Tuple[int, int, int, int]]:
        """
        Définit les zones de recherche pour Picasso avec priorité stricte.
        
        Args:
            x, y, w, h: Coordonnées du rectangle principal
            image_shape: Dimensions de l'image complète
            
        Returns:
            Dictionnaire des zones de recherche avec leurs coordonnées
        """
        img_h, img_w = image_shape[:2]
        
        # Zones de recherche avec priorité stricte
        zones = {}
        
        # 1. Petite bande sous l'image (30-80px de haut, padding horizontal)
        band_height = min(80, max(30, h // 10))
        zones['bande_sous_petite'] = (
            max(0, x - w//4), 
            min(img_h - band_height, y + h), 
            min(img_w - max(0, x - w//4), w + w//2), 
            band_height
        )
        
        # 2. Bande plus large sous l'image (40-100px de haut, plus de padding)
        band_height = min(100, max(40, h // 8))
        zones['bande_sous_large'] = (
            max(0, x - w//3), 
            min(img_h - band_height, y + h), 
            min(img_w - max(0, x - w//3), w + 2*w//3), 
            band_height
        )
        
        # 3. Bande fine à l'intérieur en bas (20px de haut, centré sur 2/3 de largeur)
        band_height = 20
        band_width = min(w, int(w * 2/3))
        band_x = x + (w - band_width) // 2
        zones['bande_interne_bas'] = (
            band_x, 
            min(img_h - band_height, y + h - band_height), 
            band_width, 
            band_height
        )
        
        # 4. Bande fine à l'intérieur en haut (20px de haut, centré sur 2/3 de largeur)
        zones['bande_interne_haut'] = (
            band_x, 
            y, 
            band_width, 
            band_height
        )
        
        # 5. Zone à droite de l'image
        right_width = min(w//2, img_w - (x + w))
        if right_width > 0:
            zones['zone_droite'] = (
                x + w, 
                y, 
                right_width, 
                h
            )
        
        # 6. Zone à gauche de l'image
        left_width = min(w//2, x)
        if left_width > 0:
            zones['zone_gauche'] = (
                max(0, x - left_width), 
                y, 
                left_width, 
                h
            )
        
        return zones
    
    def get_collection_info(self) -> Dict[str, str]:
        """
        Retourne les informations spécifiques à la collection Picasso.
        
        Returns:
            Dictionnaire avec les informations de la collection
        """
        info = super().get_collection_info()
        info.update({
            "features": [
                "Sommaire multi-pages",
                "Détection avancée avec 6 zones de recherche",
                "OCR optimisé pour numéros courts",
                "Renommage basé sur le sommaire"
            ],
            "search_zones": 6,
            "toc_pages": "Dernières 15 pages"
        })
        return info
