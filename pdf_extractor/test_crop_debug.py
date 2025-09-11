#!/usr/bin/env python3
"""
Script de test pour déboguer le système de crop
"""

import sys
import os
sys.path.append('.')

from unified_validation_server import UnifiedValidationServer
import json

def test_crop():
    """Tester le crop avec les données que vous avez fournies"""
    
    print("🧪 TEST DE CROP DEBUG")
    print("=" * 50)
    
    # Initialiser le serveur
    server = UnifiedValidationServer()
    
    # Données de votre crop
    crop_data = {
        "x": 313, 
        "y": 264, 
        "width": 846, 
        "height": 651, 
        "originalImageWidth": 1310, 
        "originalImageHeight": 2200
    }
    
    session_path = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517"
    image_path = "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517\\page_013\\0.png"
    
    print(f"📂 Session: {session_path}")
    print(f"🖼️ Image: {image_path}")
    print(f"📊 Crop data: {crop_data}")
    print()
    
    # Vérifier que l'image existe
    full_path = os.path.join("extractions_ultra", image_path)
    if os.path.exists(full_path):
        print(f"✅ Image trouvée: {full_path}")
        
        # Obtenir les dimensions actuelles
        try:
            from PIL import Image
            img = Image.open(full_path)
            print(f"📐 Dimensions actuelles: {img.size[0]}x{img.size[1]}")
            
            # Vérifier s'il y a un backup
            backup_path = full_path + ".backup"
            if os.path.exists(backup_path):
                backup_img = Image.open(backup_path)
                print(f"💾 Backup trouvé: {backup_img.size[0]}x{backup_img.size[1]}")
            else:
                print("💾 Pas de backup trouvé")
                
        except Exception as e:
            print(f"❌ Erreur lecture image: {e}")
    else:
        print(f"❌ Image non trouvée: {full_path}")
        return
    
    print("\n🔧 Simulation du crop...")
    
    # Tester le crop
    try:
        success = server.apply_crop_to_image(session_path, image_path, crop_data)
        
        if success:
            print("✅ Test crop réussi!")
        else:
            print("❌ Test crop échoué!")
            
    except Exception as e:
        print(f"❌ Erreur test crop: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crop()
