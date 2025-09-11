#!/usr/bin/env python3
"""
Script de test pour déboguer le crop depuis page PDF
"""

import sys
import os
sys.path.append('.')

from unified_validation_server import UnifiedValidationServer
import json

def test_crop_from_pdf():
    """Tester le crop avec des coordonnées depuis la page PDF"""
    
    print("🧪 TEST CROP DEPUIS PAGE PDF")
    print("=" * 50)
    
    # Initialiser le serveur
    server = UnifiedValidationServer()
    
    # Simuler des coordonnées depuis une page PDF (2620x4400 selon les logs)
    # Sélection d'une zone d'artwork typique
    crop_data = {
        "x": 500,  # Position X sur la page PDF
        "y": 1000, # Position Y sur la page PDF
        "width": 1200,  # Largeur de l'artwork
        "height": 800,  # Hauteur de l'artwork
        "originalImageWidth": 2620,  # Dimensions de la page PDF
        "originalImageHeight": 4400,
        "displayImageWidth": 635.53125,
        "displayImageHeight": 1067.328125,
        "cropSource": "pdf_page"  # Source = page PDF
    }
    
    session_path = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517"
    image_path = "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517\\page_013\\0.png"
    
    print(f"📂 Session: {session_path}")
    print(f"🖼️ Image: {image_path}")
    print(f"📊 Crop data: {crop_data}")
    print()
    
    print("🔧 Test du crop depuis page PDF...")
    
    # Tester le crop
    try:
        success = server.apply_crop_to_image(session_path, image_path, crop_data)
        
        if success:
            print("✅ Test crop depuis PDF réussi!")
            
            # Vérifier le résultat
            full_path = os.path.join("extractions_ultra", image_path)
            if os.path.exists(full_path):
                from PIL import Image
                img = Image.open(full_path)
                print(f"📐 Résultat final: {img.size[0]}x{img.size[1]}")
                
                # Calculer le ratio largeur/hauteur
                ratio = img.size[0] / img.size[1]
                expected_ratio = crop_data["width"] / crop_data["height"]
                print(f"📊 Ratio actuel: {ratio:.2f}, attendu: {expected_ratio:.2f}")
                
                if abs(ratio - expected_ratio) < 0.2:
                    print("✅ Ratio cohérent avec la sélection!")
                else:
                    print("⚠️ Ratio différent de la sélection")
                    
        else:
            print("❌ Test crop échoué!")
            
    except Exception as e:
        print(f"❌ Erreur test crop: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crop_from_pdf()
