#!/usr/bin/env python3
"""
Script de test pour vérifier que les images validées ne bougent pas
"""

import sys
import os
sys.path.append('.')

from unified_validation_server import UnifiedValidationServer

def test_validation_no_move():
    """Tester que les images validées restent en place"""
    
    print("🧪 TEST VALIDATION - PAS DE DÉPLACEMENT")
    print("=" * 50)
    
    # Initialiser le serveur
    server = UnifiedValidationServer()
    
    # Chemin de test
    session_path = os.path.join(os.getcwd(), "extractions_ultra", "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_104703")
    image_path = "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_104703\\page_013\\0.png"
    
    print(f"📂 Session: {os.path.basename(session_path)}")
    print(f"🖼️ Image: {os.path.basename(image_path)}")
    print()
    
    # Vérifier le fichier avant
    full_image_path = os.path.join(session_path, "page_013", "0.png")
    print(f"📍 Chemin actuel: {full_image_path}")
    print(f"✅ Fichier existe: {os.path.exists(full_image_path)}")
    print()
    
    # Test validation
    print("🟢 TEST: Validation d'une image dans le dossier principal")
    result = server.save_validation_state(
        session_path=session_path,
        image_id="page13_0.png", 
        validation_state="validated",
        image_path=image_path,
        move_file=True
    )
    
    # Vérifier le fichier après
    print(f"📍 Fichier toujours au même endroit: {os.path.exists(full_image_path)}")
    print(f"✅ Résultat: {result}")
    
    if os.path.exists(full_image_path) and result:
        print("🎉 SUCCÈS: L'image validée est restée en place !")
    else:
        print("❌ ÉCHEC: L'image a été déplacée ou il y a eu une erreur")
    
    print()
    print("=" * 50)

if __name__ == "__main__":
    test_validation_no_move()
