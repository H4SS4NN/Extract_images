#!/usr/bin/env python3
"""
Test de la détection de sommaire selon les collections
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from artwork_collections import CollectionFactory
from core import PDFExtractor


def test_summary_detection():
    """Test de la détection de sommaire"""
    print("🧪 TEST DÉTECTION SOMMAIRE PAR COLLECTION")
    print("=" * 50)
    
    # Test 1: Collection Picasso (avec sommaire)
    print("\n1️⃣ Test Collection Picasso")
    picasso_collection = CollectionFactory.create_collection('picasso')
    print(f"Nom: {picasso_collection.name}")
    print(f"A des sommaires: {picasso_collection.has_summary_page()}")
    
    if picasso_collection.has_summary_page():
        summary_config = picasso_collection.get_summary_detection_config()
        print(f"Configuration sommaire:")
        print(f"  - Activé: {summary_config['enabled']}")
        print(f"  - Mots-clés: {summary_config['keywords']}")
        print(f"  - Min entries: {summary_config['min_entries']}")
    
    # Test 2: Collection Dubuffet (sans sommaire)
    print("\n2️⃣ Test Collection Dubuffet")
    dubuffet_collection = CollectionFactory.create_collection('dubuffet')
    print(f"Nom: {dubuffet_collection.name}")
    print(f"A des sommaires: {dubuffet_collection.has_summary_page()}")
    
    if dubuffet_collection.has_summary_page():
        summary_config = dubuffet_collection.get_summary_detection_config()
        print(f"Configuration sommaire: {summary_config}")
    else:
        summary_config = dubuffet_collection.get_summary_detection_config()
        print(f"Configuration sommaire (désactivée):")
        print(f"  - Activé: {summary_config['enabled']}")
        print(f"  - Mots-clés: {summary_config['keywords']}")
    
    # Test 3: Extracteur avec différentes collections
    print("\n3️⃣ Test Extracteur avec collections")
    
    print("\n📚 Extracteur Picasso:")
    extractor_picasso = PDFExtractor('picasso')
    print(f"  - Collection: {extractor_picasso.collection.name}")
    print(f"  - Recherche sommaire: {extractor_picasso.collection.has_summary_page()}")
    
    print("\n📚 Extracteur Dubuffet:")
    extractor_dubuffet = PDFExtractor('dubuffet')
    print(f"  - Collection: {extractor_dubuffet.collection.name}")
    print(f"  - Recherche sommaire: {extractor_dubuffet.collection.has_summary_page()}")
    
    print("\n✅ Tests terminés!")
    print("\n📋 Résumé:")
    print("  - Picasso: Recherche sommaire avec mots-clés spécifiques")
    print("  - Dubuffet: Pas de recherche sommaire, numéros directement détectés")


if __name__ == "__main__":
    test_summary_detection()
