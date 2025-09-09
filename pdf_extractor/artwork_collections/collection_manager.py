#!/usr/bin/env python3
"""
Gestionnaire des collections d'œuvres d'art.
Permet de choisir et gérer différentes collections.
"""

import logging
from typing import Dict, Optional
from .base_collection import BaseCollection

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Gestionnaire des collections d'œuvres d'art.
    Centralise la gestion des différentes collections disponibles.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de collections."""
        self._collections: Dict[str, BaseCollection] = {}
        self._register_default_collections()
    
    def _register_default_collections(self):
        """Enregistre les collections par défaut."""
        # Import dynamique pour éviter les imports circulaires
        try:
            from .picasso_collection import PicassoCollection
            from .dubuffet_collection import DubuffetCollection
            
            self._collections["picasso"] = PicassoCollection()
            self._collections["dubuffet"] = DubuffetCollection()
            
            logger.info(f"✅ Collections enregistrées: {list(self._collections.keys())}")
        except ImportError as e:
            logger.warning(f"⚠️ Impossible d'importer certaines collections: {e}")
    
    def get_available_collections(self) -> Dict[str, BaseCollection]:
        """
        Retourne toutes les collections disponibles.
        
        Returns:
            Dictionnaire des collections disponibles
        """
        return self._collections.copy()
    
    def get_collection(self, name: str) -> Optional[BaseCollection]:
        """
        Récupère une collection par son nom.
        
        Args:
            name: Nom de la collection
            
        Returns:
            Collection demandée ou None si non trouvée
        """
        return self._collections.get(name.lower())
    
    def register_collection(self, collection: BaseCollection):
        """
        Enregistre une nouvelle collection.
        
        Args:
            collection: Collection à enregistrer
        """
        self._collections[collection.name.lower()] = collection
        logger.info(f"✅ Collection '{collection.name}' enregistrée")
    
    def prompt_collection_choice(self) -> BaseCollection:
        """
        Affiche un menu pour choisir la collection et retourne la collection sélectionnée.
        
        Returns:
            Collection sélectionnée par l'utilisateur
        """
        collections = self.get_available_collections()
        
        if not collections:
            raise RuntimeError("❌ Aucune collection disponible")
        
        print("\n" + "="*60)
        print("📚 CHOIX DE COLLECTION")
        print("="*60)
        
        # Afficher les collections disponibles
        for i, (key, collection) in enumerate(collections.items(), 1):
            print(f"{i}. {collection.name.upper()}: {collection.description}")
        
        print(f"{len(collections) + 1}. Auto-détection")
        print("="*60)
        
        while True:
            try:
                choice = input(f"Votre choix [1-{len(collections) + 1}]: ").strip()
                
                if not choice:
                    # Choix par défaut : première collection
                    selected = list(collections.values())[0]
                    print(f"✅ Collection par défaut sélectionnée: {selected.name}")
                    return selected
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(collections):
                    selected = list(collections.values())[choice_num - 1]
                    print(f"✅ Collection sélectionnée: {selected.name}")
                    return selected
                elif choice_num == len(collections) + 1:
                    # Auto-détection
                    return self._auto_detect_collection()
                else:
                    print(f"❌ Choix invalide. Veuillez entrer un nombre entre 1 et {len(collections) + 1}")
                    
            except ValueError:
                print("❌ Veuillez entrer un nombre valide")
            except KeyboardInterrupt:
                print("\n❌ Annulé par l'utilisateur")
                raise
    
    def _auto_detect_collection(self) -> BaseCollection:
        """
        Tente de détecter automatiquement la collection.
        Pour l'instant, retourne la collection par défaut.
        
        Returns:
            Collection détectée automatiquement
        """
        # TODO: Implémenter la logique d'auto-détection
        # Pour l'instant, retourner la première collection disponible
        collections = list(self.get_available_collections().values())
        default_collection = collections[0]
        
        print(f"🔍 Auto-détection: {default_collection.name} (par défaut)")
        return default_collection
    
    def list_collections(self):
        """Affiche la liste des collections disponibles."""
        collections = self.get_available_collections()
        
        if not collections:
            print("❌ Aucune collection disponible")
            return
        
        print("\n📚 Collections disponibles:")
        print("-" * 40)
        
        for name, collection in collections.items():
            info = collection.get_collection_info()
            print(f"• {name.upper()}: {info['description']}")
            print(f"  - Sommaire: {'Oui' if info['has_toc'] else 'Non'}")
        
        print("-" * 40)
