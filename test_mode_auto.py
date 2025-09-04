#!/usr/bin/env python3
"""
Script de test pour le MODE AUTOMATIQUE COMPLET
"""

import requests
import json
import time
import os

def test_mode_automatique():
    """Test du mode automatique complet"""
    
    base_url = "http://localhost:5000"
    
    print("🤖 TEST MODE AUTOMATIQUE COMPLET")
    print("=" * 60)
    
    # Test de connexion
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Serveur connecté")
        else:
            print("❌ Serveur non accessible")
            return
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return
    
    print("\n🎯 QUE FAIT LE MODE AUTOMATIQUE:")
    print("=" * 60)
    
    print("1. 🎯 DÉTECTION INTELLIGENTE")
    print("   • Analyse automatique de chaque page/image")
    print("   • Test de plusieurs configurations")
    print("   • Choix automatique de la meilleure")
    print("   • Pas de paramètres à configurer!")
    
    print("\n2. 🖼️ EXTRACTION AUTOMATIQUE")
    print("   • Extraction immédiate de chaque rectangle")
    print("   • Redressement automatique des perspectives")
    print("   • Sauvegarde PNG haute qualité")
    
    print("\n3. 💾 SAUVEGARDE TEMPS RÉEL")
    print("   • Dossier unique avec timestamp")
    print("   • Organisation intelligente:")
    print("     - avec_numeros/ (si numéros d'œuvre détectés)")
    print("     - sans_numeros/ (rectangles sans numéros)")
    print("     - miniatures/ (aperçus 200px)")
    
    print("\n4. 📊 LOGS JSON DÉTAILLÉS")
    print("   • Un fichier page_XXX_log.json par page")
    print("   • complete_log.json avec résumé global")
    print("   • Toutes les infos de debug dedans!")
    
    print("\n5. 📁 RÉSULTATS IMMÉDIATS")
    print("   • Ouverture automatique du dossier")
    print("   • Résumé HTML avec galerie")
    print("   • Tout est prêt à utiliser!")
    
    print("\n📋 EXEMPLE DE LOG JSON PAR PAGE:")
    print("=" * 60)
    
    example_page_log = {
        "page": 1,
        "timestamp": "2024-01-15T14:30:25",
        "status": "success",
        "page_analysis": {
            "width_mm": 210.0,
            "height_mm": 297.0,
            "page_format": "A4",
            "recommended_dpi": 300
        },
        "dpi_used": 300,
        "image_size": "2480x3508",
        "config_used": "high_contrast_standard",
        "rectangles_found": 3,
        "rectangles_details": [
            {
                "rect_id": 1,
                "artwork_number": "1234",
                "bbox": {"x": 100, "y": 200, "w": 300, "h": 400},
                "area": 120000,
                "saved_path": "extractions/.../oeuvre_1234_p001.png",
                "filename": "oeuvre_1234_p001.png"
            },
            {
                "rect_id": 2,
                "artwork_number": None,
                "bbox": {"x": 500, "y": 600, "w": 200, "h": 250},
                "area": 50000,
                "saved_path": "extractions/.../page_001_rect_02.png",
                "filename": "page_001_rect_02.png"
            }
        ],
        "saved_images": [
            "oeuvre_1234_p001.png",
            "page_001_rect_02.png"
        ],
        "processing_time": 2.45
    }
    
    print(json.dumps(example_page_log, indent=2, ensure_ascii=False))
    
    print("\n📊 EXEMPLE DE LOG COMPLET:")
    print("=" * 60)
    
    example_complete_log = {
        "session_info": {
            "pdf_name": "catalogue.pdf",
            "session_dir": "extractions/catalogue_20240115_143025",
            "start_time": "2024-01-15T14:30:25",
            "total_pages": 50,
            "total_saved": 125,
            "mode": "auto_realtime"
        },
        "summary": {
            "successful_pages": 48,
            "failed_pages": 2,
            "total_rectangles": 125,
            "configs_used": [
                "high_contrast_standard",
                "normal_balanced", 
                "low_contrast_enhanced"
            ]
        }
    }
    
    print(json.dumps(example_complete_log, indent=2, ensure_ascii=False))
    
    print("\n🔍 COMMENT VOIR CE QUI NE VA PAS:")
    print("=" * 60)
    
    print("1. 📁 Ouvrir le dossier généré automatiquement")
    print("2. 📄 Regarder page_XXX_log.json pour une page problématique")
    print("3. 🔍 Vérifier:")
    print("   • status: 'success', 'failed', ou 'error'")
    print("   • config_used: quelle config a été choisie")
    print("   • rectangles_found: combien trouvés")
    print("   • rectangles_details: détails de chaque rectangle")
    print("   • processing_time: temps de traitement")
    print("   • error: message d'erreur si problème")
    
    print("\n4. 📊 Regarder complete_log.json pour vue d'ensemble")
    print("5. 🖼️ Vérifier les miniatures/ pour aperçu rapide")
    print("6. 📋 Ouvrir resume.html pour galerie interactive")
    
    print("\n🚀 UTILISATION:")
    print("=" * 60)
    
    print("1. Démarrer le serveur: python backend2.py")
    print("2. Envoyer POST vers /upload_auto avec ton PDF")
    print("3. Attendre (les WebSockets montrent la progression)")
    print("4. Le dossier s'ouvre automatiquement à la fin!")
    print("5. Tout est dedans: images + logs + résumé")
    
    print("\n🎉 AVANTAGES:")
    print("=" * 60)
    
    print("✅ ZÉRO configuration - tout est automatique")
    print("✅ Résultats IMMÉDIATS - sauvegarde temps réel")
    print("✅ LOGS COMPLETS - debug facile")
    print("✅ ORGANISATION intelligente - facile à naviguer")
    print("✅ APERÇUS rapides - miniatures + galerie HTML")
    print("✅ OUVERTURE automatique - pas besoin de chercher")
    print("✅ COMPATIBLE avec tous formats PDF/images")
    
    print(f"\n🤖 MODE AUTOMATIQUE prêt sur {base_url}/upload_auto")
    print("📁 Les résultats seront dans le dossier 'extractions/'")
    
    # Vérifier si le dossier extractions existe
    if os.path.exists("extractions"):
        sessions = [d for d in os.listdir("extractions") if os.path.isdir(os.path.join("extractions", d))]
        if sessions:
            print(f"\n📊 Sessions précédentes trouvées: {len(sessions)}")
            print("Exemples de dossiers générés:")
            for session in sessions[-3:]:
                print(f"   📁 {session}")
                session_path = os.path.join("extractions", session)
                if os.path.exists(session_path):
                    files = os.listdir(session_path)
                    json_files = [f for f in files if f.endswith('.json')]
                    if json_files:
                        print(f"      📄 Logs JSON: {len(json_files)} fichiers")

if __name__ == "__main__":
    test_mode_automatique()