"""
Classe de base pour les collections d'œuvres d'art
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
import numpy as np


class ArtworkCollection(ABC):
    """
    Classe de base pour définir les spécificités de chaque collection d'artiste
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    def get_detection_zones(self, image: np.ndarray, rectangle: dict) -> List[Tuple[int, int, int, int]]:
        """
        Définit les zones de recherche prioritaires pour détecter les numéros d'œuvres
        
        Args:
            image: Image de la page
            rectangle: Rectangle détecté contenant l'œuvre
            
        Returns:
            Liste de tuples (x, y, w, h) définissant les zones de recherche par priorité
        """
        pass
    
    @abstractmethod
    def get_number_validation_rules(self) -> Dict:
        """
        Retourne les règles de validation des numéros pour cette collection
        
        Returns:
            Dict contenant les règles (min_length, max_length, patterns, exclusions, etc.)
        """
        pass
    
    @abstractmethod
    def get_ocr_config(self) -> Dict:
        """
        Configuration OCR spécifique à cette collection
        
        Returns:
            Dict avec les paramètres OCR (psm, whitelist, preprocessing, etc.)
        """
        pass
    
    def get_scoring_weights(self) -> Dict:
        """
        Poids pour le scoring des détections (peut être surchargé)
        
        Returns:
            Dict avec les poids pour chaque zone et critère
        """
        return {
            'zone_weights': [4.0, 3.5, 3.0, 2.5, 1.5, 1.5],  # Poids par zone
            'length_bonus': {1: 2.0, 2: 2.0, 3: 2.0, 4: 1.0, 5: 0.8, 6: 0.6},
            'proximity_bonus': 1.2,
            'early_stop_threshold': 8.0
        }
    
    def has_summary_page(self) -> bool:
        """
        Indique si cette collection a des pages de sommaire
        """
        return True
    
    def get_summary_detection_config(self) -> Dict:
        """
        Configuration pour la détection des sommaires (si applicable)
        """
        return {
            'enabled': self.has_summary_page(),
            'keywords': ['sommaire', 'table', 'contents', 'index'],
            'min_entries': 5
        }
    
    def preprocess_number(self, number_str: str) -> Optional[str]:
        """
        Préprocessing spécifique du numéro détecté (peut être surchargé)
        
        Args:
            number_str: Numéro brut détecté
            
        Returns:
            Numéro nettoyé ou None si invalide
        """
        if not number_str or not number_str.isdigit():
            return None
            
        # Règles par défaut
        rules = self.get_number_validation_rules()
        
        if len(number_str) < rules.get('min_length', 1):
            return None
        if len(number_str) > rules.get('max_length', 6):
            return None
            
        # Exclusion des années probables
        if len(number_str) == 4 and int(number_str) > 1899:
            return None
            
        return number_str
    
    def get_collection_info(self) -> Dict:
        """
        Informations sur la collection
        """
        return {
            'name': self.name,
            'description': self.description,
            'has_summary': self.has_summary_page(),
            'detection_zones_count': len(self.get_detection_zones(np.zeros((100, 100, 3)), {'bbox': {'x': 0, 'y': 0, 'w': 50, 'h': 50}})),
            'validation_rules': self.get_number_validation_rules()
        }
