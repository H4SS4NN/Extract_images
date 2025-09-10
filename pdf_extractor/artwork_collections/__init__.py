"""
Module de gestion des collections d'œuvres d'art
Permet de gérer différents artistes avec leurs spécificités de détection
"""

from .base_collection import ArtworkCollection
from .picasso_collection import PicassoCollection
from .dubuffet_collection import DubuffetCollection
from .collection_factory import CollectionFactory

__all__ = [
    'ArtworkCollection',
    'PicassoCollection', 
    'DubuffetCollection',
    'CollectionFactory'
]
