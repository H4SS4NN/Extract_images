#!/usr/bin/env python3
"""
Collection Dubuffet - Gestion des œuvres de Jean Dubuffet.
Détection des numéros directement sous les œuvres, pas de sommaire central.
"""

import logging
import cv2
import numpy as np
from typing import Dict, Optional, List, Tuple
from .base_collection import BaseCollection

logger = logging.getLogger(__name__)


class DubuffetCollection(BaseCollection):
    """
    Collection pour les œuvres de Jean Dubuffet.
    Pas de sommaire central, détection des numéros sous les œuvres.
    """
    
    def __init__(self):
        super().__init__(
            name="dubuffet",
            description="Collection Dubuffet avec numéros sous les œuvres (pas de sommaire central)"
        )
        self.logger = logging.getLogger(f"{__name__}.dubuffet")
        self._extraction_counter = 0  # Compteur pour le fallback séquentiel
    
    def extract_toc(self, pdf_path: str) -> Optional[Dict]:
        """
        Pas de sommaire pour Dubuffet.
        
        Args:
            pdf_path: Chemin vers le PDF
            
        Returns:
            None (pas de sommaire)
        """
        self.logger.info("ℹ️ Collection Dubuffet: pas de sommaire central")
        return None
    
    def detect_artwork_number(self, image, rectangle: Dict, page_context: Dict) -> Optional[str]:
        """
        Détecte le numéro d'œuvre dans une image Dubuffet.
        Cherche directement sous l'œuvre, fallback séquentiel si non trouvé.
        
        Args:
            image: Image extraite (numpy array)
            rectangle: Dictionnaire contenant les coordonnées du rectangle
            page_context: Contexte de la page
            
        Returns:
            Numéro d'œuvre détecté (string) ou numéro séquentiel
        """
        try:
            # 1. Essayer de détecter le numéro sous l'œuvre
            detected_number = self._detect_artwork_number_dubuffet(image, rectangle)
            
            if detected_number:
                self.logger.debug(f"🔍 Numéro détecté sous l'œuvre: {detected_number}")
                return detected_number
            
            # 2. Fallback: numéro séquentiel d'extraction
            self._extraction_counter += 1
            fallback_number = f"extraction_{self._extraction_counter:03d}"
            self.logger.info(f"🔄 Fallback séquentiel: {fallback_number}")
            return fallback_number
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la détection du numéro: {e}")
            # Fallback en cas d'erreur
            self._extraction_counter += 1
            return f"extraction_{self._extraction_counter:03d}"
    
    def _detect_artwork_number_dubuffet(self, image: np.ndarray, rectangle: Dict) -> Optional[str]:
        """
        Détecte le numéro d'œuvre spécifiquement pour Dubuffet.
        Zone de recherche restrictive: directement sous l'œuvre.
        
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
            
            # Zone de recherche restrictive: directement sous l'œuvre
            search_zone = self._get_dubuffet_search_zone(x, y, w, h, image.shape)
            
            if search_zone is None:
                return None
            
            zone_x, zone_y, zone_w, zone_h = search_zone
            
            # Extraire la zone
            zone = image[zone_y:zone_y+zone_h, zone_x:zone_x+zone_w]
            
            if zone.size == 0:
                return None
            
            # Préprocessing pour améliorer la détection
            zone_processed = self._preprocess_zone_for_ocr(zone)
            
            # OCR optimisé pour les numéros courts (1-3 chiffres en priorité)
            config = "--psm 7 -c tessedit_char_whitelist=0123456789"
            text = pytesseract.image_to_string(zone_processed, config=config)
            
            # Chercher des numéros de 1-3 chiffres en priorité, puis 1-6 chiffres
            patterns = [
                r"\b\d{1,3}\b",  # Priorité: 1-3 chiffres
                r"\b\d{1,6}\b"   # Fallback: 1-6 chiffres
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # Prendre le premier match (le plus probable)
                    number = matches[0]
                    self.logger.debug(f"🔍 Numéro détecté: {number} (pattern: {pattern})")
                    return number
            
            self.logger.debug("🔍 Aucun numéro détecté sous l'œuvre")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la détection Dubuffet: {e}")
            return None
    
    def _get_dubuffet_search_zone(self, x: int, y: int, w: int, h: int, 
                                 image_shape: Tuple[int, int, int]) -> Optional[Tuple[int, int, int, int]]:
        """
        Définit la zone de recherche restrictive pour Dubuffet.
        Zone plus petite et plus ciblée que Picasso.
        
        Args:
            x, y, w, h: Coordonnées du rectangle principal
            image_shape: Dimensions de l'image complète
            
        Returns:
            Coordonnées de la zone de recherche ou None
        """
        img_h, img_w = image_shape[:2]
        
        # Zone restrictive: bande fine directement sous l'œuvre
        # Hauteur: 15-40px, largeur: centrée sur l'œuvre avec padding minimal
        zone_height = min(40, max(15, h // 15))
        zone_width = min(w + w//4, img_w - x)  # Largeur avec padding minimal
        
        # Centrer la zone sur l'œuvre
        zone_x = max(0, x - w//8)
        zone_y = min(img_h - zone_height, y + h)
        
        # Vérifier que la zone est valide
        if zone_x + zone_width > img_w or zone_y + zone_height > img_h:
            return None
        
        return (zone_x, zone_y, zone_width, zone_height)
    
    def _preprocess_zone_for_ocr(self, zone: np.ndarray) -> np.ndarray:
        """
        Préprocesse la zone d'image pour améliorer la détection OCR.
        
        Args:
            zone: Zone d'image à traiter
            
        Returns:
            Zone préprocessée
        """
        try:
            # Convertir en niveaux de gris si nécessaire
            if len(zone.shape) == 3:
                gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
            else:
                gray = zone.copy()
            
            # Améliorer le contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Binarisation adaptative
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Morphologie pour nettoyer
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception as e:
            self.logger.debug(f"Erreur preprocessing: {e}")
            return zone
    
    def create_artwork_json(self, image_path, plate_number: int, 
                           plate_info: Dict, artist_name: str, 
                           image_size: Tuple[int, int]) -> Dict:
        """
        Crée le JSON d'une œuvre Dubuffet.
        Adapté pour les œuvres sans sommaire.
        
        Args:
            image_path: Chemin vers l'image
            plate_number: Numéro de la planche (peut être "extraction_XXX")
            plate_info: Informations de la planche (vide pour Dubuffet)
            artist_name: Nom de l'artiste
            image_size: Taille de l'image (width, height)
            
        Returns:
            Dictionnaire JSON de l'œuvre
        """
        import uuid
        from datetime import datetime
        
        # Générer un ID unique
        artwork_id = str(uuid.uuid4())
        
        # Pour Dubuffet, pas de titre depuis le sommaire
        title = f"Œuvre {plate_number}" if isinstance(plate_number, int) else str(plate_number)
        
        # Calculer les dimensions en cm (approximation basée sur DPI 400)
        dpi = 400
        width_cm = round((image_size[0] / dpi) * 2.54, 1)
        height_cm = round((image_size[1] / dpi) * 2.54, 1)
        
        # Créer la description
        description = f"{artist_name}, {title}. Medium: No comment. Size: {width_cm} x {height_cm} cm. Execution year: No comment."
        
        artwork_json = {
            "artist_name": artist_name,
            "title": title,
            "id": artwork_id,
            "image_url": str(image_path),
            "size": [width_cm, height_cm],
            "size_unit": "cm",
            "medium": "No comment",
            "signature": "No comment",
            "execution_year": "No comment",
            "description": description,
            "provenance": ["No comment"],
            "literature": ["No comment"],
            "exhibition": ["No comment"],
            "plate_number": plate_number,
            "source_page": None,
            "extraction_date": datetime.now().isoformat(),
            "collection_type": "dubuffet",
            "detection_method": "sequential_fallback" if "extraction_" in str(plate_number) else "under_artwork"
        }
        
        return artwork_json
    
    def get_collection_info(self) -> Dict[str, str]:
        """
        Retourne les informations spécifiques à la collection Dubuffet.
        
        Returns:
            Dictionnaire avec les informations de la collection
        """
        info = super().get_collection_info()
        info.update({
            "features": [
                "Pas de sommaire central",
                "Détection sous les œuvres",
                "Fallback séquentiel",
                "Zone de recherche restrictive",
                "OCR optimisé pour numéros courts"
            ],
            "search_zones": 1,
            "fallback": "Numérotation séquentielle",
            "toc_pages": "Aucun"
        })
        return info
