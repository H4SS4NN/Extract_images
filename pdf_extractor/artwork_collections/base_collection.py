#!/usr/bin/env python3
"""
Classe de base pour toutes les collections d'œuvres d'art.
Définit l'interface commune pour l'extraction et la détection.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseCollection(ABC):
    """
    Classe de base pour toutes les collections d'œuvres d'art.
    Chaque collection doit implémenter ses propres méthodes de détection.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialise une collection.
        
        Args:
            name: Nom de la collection (ex: "picasso", "dubuffet")
            description: Description de la collection
        """
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def extract_toc(self, pdf_path: str) -> Optional[Dict]:
        """
        Extrait le sommaire/table des planches du PDF.
        
        Args:
            pdf_path: Chemin vers le PDF
            
        Returns:
            Dictionnaire contenant les données du sommaire ou None si pas de sommaire
        """
        pass
    
    @abstractmethod
    def detect_artwork_number(self, image, rectangle: Dict, page_context: Dict) -> Optional[str]:
        """
        Détecte le numéro d'œuvre dans une image extraite.
        
        Args:
            image: Image extraite (numpy array)
            rectangle: Dictionnaire contenant les coordonnées du rectangle
            page_context: Contexte de la page (numéro, détections précédentes, etc.)
            
        Returns:
            Numéro d'œuvre détecté (string) ou None si non trouvé
        """
        pass
    
    def get_artist_name(self, pdf_path: str) -> str:
        """
        Extrait le nom de l'artiste depuis le nom du fichier PDF.
        
        Args:
            pdf_path: Chemin vers le PDF
            
        Returns:
            Nom de l'artiste formaté
        """
        import sys
        from pathlib import Path
        # Ajouter le répertoire parent au path pour les imports
        sys.path.append(str(Path(__file__).parent.parent))
        from toc_planches import extract_artist_name_from_pdf
        return extract_artist_name_from_pdf(pdf_path)
    
    def create_artwork_json(self, image_path: Path, plate_number: int, 
                           plate_info: Dict, artist_name: str, 
                           image_size: Tuple[int, int]) -> Dict:
        """
        Crée le JSON d'une œuvre d'art.
        
        Args:
            image_path: Chemin vers l'image
            plate_number: Numéro de la planche
            plate_info: Informations de la planche
            artist_name: Nom de l'artiste
            image_size: Taille de l'image (width, height)
            
        Returns:
            Dictionnaire JSON de l'œuvre
        """
        import sys
        from pathlib import Path
        # Ajouter le répertoire parent au path pour les imports
        sys.path.append(str(Path(__file__).parent.parent))
        from toc_planches import create_artwork_json
        return create_artwork_json(image_path, plate_number, plate_info, artist_name, image_size)
    
    def save_artwork_json(self, artwork_data: Dict, output_dir: Path, plate_number: int) -> Path:
        """
        Sauvegarde le JSON d'une œuvre.
        
        Args:
            artwork_data: Données de l'œuvre
            output_dir: Dossier de sortie
            plate_number: Numéro de la planche
            
        Returns:
            Chemin vers le fichier JSON créé
        """
        import sys
        from pathlib import Path
        # Ajouter le répertoire parent au path pour les imports
        sys.path.append(str(Path(__file__).parent.parent))
        from toc_planches import save_artwork_json
        return save_artwork_json(artwork_data, output_dir, plate_number)
    
    def get_collection_info(self) -> Dict[str, str]:
        """
        Retourne les informations sur la collection.
        
        Returns:
            Dictionnaire avec les informations de la collection
        """
        return {
            "name": self.name,
            "description": self.description,
            "has_toc": self.extract_toc is not None
        }
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"
