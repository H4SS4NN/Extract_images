#!/usr/bin/env python3
"""
Script de test pour le système multi-collections
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from artwork_collections import CollectionFactory, PicassoCollection, DubuffetCollection
from core import PDFExtractor


def test_collections():
    """Test des collections disponibles"""
    print("🧪 TEST DU SYSTÈME MULTI-COLLECTIONS")
    print("=" * 50)
    
    # Test 1: Factory
    print("\n1️⃣ Test de la Factory")
    available = CollectionFactory.get_available_collections()
    print(f"Collections disponibles: {available}")
    
    # Test 2: Création des collections
    print("\n2️⃣ Test de création des collections")
    
    picasso = CollectionFactory.create_collection('picasso')
    print(f"Picasso: {picasso.name if picasso else 'ERREUR'}")
    
    dubuffet = CollectionFactory.create_collection('dubuffet')
    print(f"Dubuffet: {dubuffet.name if dubuffet else 'ERREUR'}")
    
    # Test 3: Informations des collections
    print("\n3️⃣ Informations des collections")
    
    if picasso:
        info = picasso.get_collection_info()
        print(f"📚 {info['name']}: {info['description']}")
        print(f"   - Sommaires: {info['has_summary']}")
        print(f"   - Zones: {info['detection_zones_count']}")
        print(f"   - Règles: {info['validation_rules']}")
    
    if dubuffet:
        info = dubuffet.get_collection_info()
        print(f"📚 {info['name']}: {info['description']}")
        print(f"   - Sommaires: {info['has_summary']}")
        print(f"   - Zones: {info['detection_zones_count']}")
        print(f"   - Règles: {info['validation_rules']}")
    
    # Test 4: Configuration OCR
    print("\n4️⃣ Configuration OCR")
    
    if picasso:
        ocr_config = picasso.get_ocr_config()
        print(f"Picasso OCR: {len(ocr_config['psm_configs'])} configurations")
        print(f"   - Scale: {ocr_config['scale_factor']}")
        print(f"   - Preprocessing: {ocr_config['preprocessing']}")
    
    if dubuffet:
        ocr_config = dubuffet.get_ocr_config()
        print(f"Dubuffet OCR: {len(ocr_config['psm_configs'])} configurations")
        print(f"   - Scale: {ocr_config['scale_factor']}")
        print(f"   - Preprocessing: {ocr_config['preprocessing']}")
    
    # Test 5: Zones de détection (avec image factice)
    print("\n5️⃣ Zones de détection")
    import numpy as np
    
    fake_image = np.zeros((1000, 800, 3), dtype=np.uint8)
    fake_rect = {'bbox': {'x': 100, 'y': 200, 'w': 300, 'h': 400}}
    
    if picasso:
        zones_p = picasso.get_detection_zones(fake_image, fake_rect)
        print(f"Picasso: {len(zones_p)} zones de détection")
        print(f"   - Zone 1: {zones_p[0] if zones_p else 'Aucune'}")
    
    if dubuffet:
        zones_d = dubuffet.get_detection_zones(fake_image, fake_rect)
        print(f"Dubuffet: {len(zones_d)} zones de détection")
        print(f"   - Zone 1: {zones_d[0] if zones_d else 'Aucune'}")
    
    # Test 6: PDFExtractor avec collections
    print("\n6️⃣ Test PDFExtractor")
    
    extractor_default = PDFExtractor()
    print(f"Extracteur par défaut: {extractor_default.collection.name}")
    
    extractor_picasso = PDFExtractor('picasso')
    print(f"Extracteur Picasso: {extractor_picasso.collection.name}")
    
    extractor_dubuffet = PDFExtractor('dubuffet')
    print(f"Extracteur Dubuffet: {extractor_dubuffet.collection.name}")
    
    # Test 7: Changement de collection
    print("\n7️⃣ Test changement de collection")
    
    success = extractor_default.set_collection('dubuffet')
    print(f"Changement vers Dubuffet: {'✅' if success else '❌'}")
    print(f"Collection actuelle: {extractor_default.collection.name}")
    
    # Test 8: Auto-détection
    print("\n8️⃣ Test auto-détection")
    
    test_paths = [
        "catalogue_picasso_2023.pdf",
        "jean_dubuffet_oeuvres.pdf",
        "document_inconnu.pdf"
    ]
    
    for path in test_paths:
        detected = CollectionFactory.auto_detect_collection(path, "")
        print(f"{path}: {detected if detected else 'Non détecté'}")
    
    print("\n✅ Tests terminés avec succès!")


if __name__ == "__main__":
    test_collections()
