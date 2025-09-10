"""
Factory pour créer les collections d'œuvres d'art
"""

from typing import Dict, List, Optional
from .base_collection import ArtworkCollection
from .picasso_collection import PicassoCollection
from .dubuffet_collection import DubuffetCollection


class CollectionFactory:
    """
    Factory pour créer et gérer les différentes collections d'artistes
    """
    
    # Registre des collections disponibles
    _collections = {
        'picasso': PicassoCollection,
        'dubuffet': DubuffetCollection,
    }
    
    # Alias pour faciliter la sélection
    _aliases = {
        'pablo': 'picasso',
        'pablo_picasso': 'picasso',
        'jean_dubuffet': 'dubuffet',
        'jean': 'dubuffet',
    }
    
    @classmethod
    def create_collection(cls, collection_name: str) -> Optional[ArtworkCollection]:
        """
        Crée une instance de collection basée sur le nom
        
        Args:
            collection_name: Nom de la collection (insensible à la casse)
            
        Returns:
            Instance de la collection ou None si non trouvée
        """
        # Normaliser le nom
        name = collection_name.lower().strip().replace(' ', '_').replace('-', '_')
        
        # Vérifier les alias
        if name in cls._aliases:
            name = cls._aliases[name]
        
        # Créer la collection
        if name in cls._collections:
            return cls._collections[name]()
        
        return None
    
    @classmethod
    def get_available_collections(cls) -> List[str]:
        """
        Retourne la liste des collections disponibles
        
        Returns:
            Liste des noms de collections
        """
        return list(cls._collections.keys())
    
    @classmethod
    def get_collection_info(cls) -> Dict[str, Dict]:
        """
        Retourne les informations sur toutes les collections
        
        Returns:
            Dict avec les infos de chaque collection
        """
        info = {}
        for name, collection_class in cls._collections.items():
            collection = collection_class()
            info[name] = collection.get_collection_info()
        return info
    
    @classmethod
    def register_collection(cls, name: str, collection_class: type, aliases: List[str] = None):
        """
        Enregistre une nouvelle collection
        
        Args:
            name: Nom de la collection
            collection_class: Classe de la collection
            aliases: Liste d'alias optionnels
        """
        if not issubclass(collection_class, ArtworkCollection):
            raise ValueError("La classe doit hériter de ArtworkCollection")
        
        cls._collections[name.lower()] = collection_class
        
        if aliases:
            for alias in aliases:
                cls._aliases[alias.lower()] = name.lower()
    
    @classmethod
    def auto_detect_collection(cls, pdf_path: str, extracted_text: str = "") -> Optional[str]:
        """
        Tentative de détection automatique de la collection basée sur le contenu
        
        Args:
            pdf_path: Chemin du PDF
            extracted_text: Texte extrait du PDF
            
        Returns:
            Nom de la collection détectée ou None
        """
        # Mots-clés pour chaque collection
        keywords = {
            'picasso': ['picasso', 'pablo', 'catalogue raisonné', 'zervos'],
            'dubuffet': ['dubuffet', 'jean dubuffet', 'art brut'],
        }
        
        # Texte à analyser (nom du fichier + texte extrait)
        text_to_analyze = (pdf_path.lower() + " " + extracted_text.lower()).replace('_', ' ')
        
        # Compter les correspondances
        scores = {}
        for collection, words in keywords.items():
            score = sum(1 for word in words if word in text_to_analyze)
            if score > 0:
                scores[collection] = score
        
        # Retourner la collection avec le meilleur score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return None
    
    @classmethod
    def get_default_collection(cls) -> str:
        """
        Retourne le nom de la collection par défaut (Picasso pour la compatibilité)
        """
        return 'picasso'
