#!/usr/bin/env python3
"""
Script de test pour vérifier les métadonnées d'extraction
"""

import sys
import os
sys.path.append('.')

from unified_validation_server import UnifiedValidationServer

def test_extraction_metadata():
    """Tester la récupération des métadonnées d'extraction"""
    
    print("🧪 TEST MÉTADONNÉES D'EXTRACTION")
    print("=" * 50)
    
    # Initialiser le serveur
    server = UnifiedValidationServer()
    
    # Chemin de test (utiliser le dossier existant)
    session_path = os.path.join(os.getcwd(), "extractions_ultra", "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_104703")
    image_path = "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_104703\\page_013\\0.png"
    
    print(f"📂 Session: {session_path}")
    print(f"🖼️ Image: {image_path}")
    print()
    
    # Récupérer les métadonnées
    metadata = server.get_extraction_metadata(session_path, image_path)
    
    if metadata:
        print("✅ Métadonnées récupérées avec succès !")
        print(f"📐 Dimensions de la page: {metadata['page_width']}×{metadata['page_height']}")
        print(f"🎯 DPI: {metadata['dpi']}")
        print(f"📦 Bbox original: {metadata['original_bbox']}")
        print(f"✂️ A été croppée: {metadata['was_cropped']}")
        print()
        print("📄 Métadonnées complètes:")
        for key, value in metadata.items():
            print(f"   {key}: {value}")
    else:
        print("❌ Impossible de récupérer les métadonnées")
    
    print()
    print("=" * 50)

if __name__ == "__main__":
    test_extraction_metadata()
