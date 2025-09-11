#!/usr/bin/env python3
"""
Script de test pour vérifier le nouveau comportement de validation
"""

import sys
import os
sys.path.append('.')

from unified_validation_server import UnifiedValidationServer

def test_validation_behavior():
    """Tester que validated reste en place et rejected va en DOUTEUX"""
    
    print("🧪 TEST COMPORTEMENT VALIDATION")
    print("=" * 50)
    
    # Initialiser le serveur
    server = UnifiedValidationServer()
    
    session_path = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517"
    image_path = "DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-multi-pagepdfocr 2_ULTRA_20250911_090517\\page_013\\0.png"
    
    print(f"📂 Session: {session_path}")
    print(f"🖼️ Image: {image_path}")
    print()
    
    # Test 1: Validation - l'image doit rester en place
    print("🟢 TEST 1: Image VALIDATED (doit rester en place)")
    print("-" * 40)
    
    # Vérifier l'emplacement actuel
    full_path = os.path.join("extractions_ultra", image_path)
    if os.path.exists(full_path):
        print(f"📍 Image actuelle: {full_path}")
        
        # Simuler une validation
        success = server.save_validation_state(
            session_path, 
            "page2_0.png", 
            "validated", 
            image_path, 
            True  # move_file = True
        )
        
        if success:
            # Vérifier que l'image est toujours au même endroit
            if os.path.exists(full_path):
                print("✅ SUCCÈS: Image validée reste en place")
            else:
                print("❌ ÉCHEC: Image validée a été déplacée")
                # Chercher où elle a été déplacée
                import glob
                pattern = os.path.join("extractions_ultra", session_path, "page_013", "**", "0.png")
                found = glob.glob(pattern, recursive=True)
                if found:
                    print(f"🔍 Image trouvée dans: {found}")
        else:
            print("❌ ÉCHEC: Erreur lors de la validation")
    else:
        print(f"❌ Image non trouvée: {full_path}")
    
    print()
    print("🔴 TEST 2: Image REJECTED (doit aller en DOUTEUX)")
    print("-" * 40)
    
    # Simuler un rejet
    success = server.save_validation_state(
        session_path,
        "page2_0.png",
        "rejected",
        image_path,
        True  # move_file = True
    )
    
    if success:
        # Vérifier que l'image a été déplacée vers DOUTEUX
        douteux_path = os.path.join("extractions_ultra", session_path, "page_013", "qualite_DOUTEUSE")
        
        if os.path.exists(douteux_path):
            import glob
            douteux_files = glob.glob(os.path.join(douteux_path, "*0.png"))
            if douteux_files:
                print(f"✅ SUCCÈS: Image rejetée déplacée vers: {douteux_files[0]}")
            else:
                print("❌ ÉCHEC: Image rejetée non trouvée dans DOUTEUX")
        else:
            print("❌ ÉCHEC: Dossier DOUTEUX non créé")
    else:
        print("❌ ÉCHEC: Erreur lors du rejet")

if __name__ == "__main__":
    test_validation_behavior()
