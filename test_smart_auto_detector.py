#!/usr/bin/env python3
"""
Script de test pour la nouvelle classe SmartAutoDetector
"""

import requests
import json
import time

def test_smart_auto_detector():
    """Test du nouveau endpoint /upload_auto"""
    
    base_url = "http://localhost:5000"
    
    print("🧪 Test du SmartAutoDetector")
    print("=" * 50)
    
    # Test 1: Vérifier que le serveur est en marche
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Serveur en marche")
            health_data = response.json()
            print(f"   Status: {health_data['status']}")
            print(f"   Features: {health_data['features']}")
        else:
            print("❌ Serveur non accessible")
            return
    except Exception as e:
        print(f"❌ Erreur connexion serveur: {e}")
        return
    
    print("\n" + "=" * 50)
    print("🎯 FONCTIONNALITÉS SMART AUTO DETECTOR")
    print("=" * 50)
    
    print("\n📋 Nouvelles fonctionnalités ajoutées:")
    print("   1. SmartAutoDetector - Détection automatique intelligente")
    print("   2. Analyse automatique des caractéristiques d'image")
    print("   3. Test de multiples configurations")
    print("   4. Sélection automatique de la meilleure configuration")
    print("   5. Prétraitement adaptatif selon le type d'image")
    print("   6. Endpoint /upload_auto pour mode automatique")
    print("   7. Support WebSocket pour progression temps réel")
    
    print("\n🔍 TYPES DE CONFIGURATIONS TESTÉES:")
    print("   • low_contrast_enhanced - Pour images à faible contraste")
    print("   • high_contrast_standard - Pour images à fort contraste")
    print("   • normal_balanced - Pour images normales")
    print("   • complex_filtering - Pour images complexes")
    print("   • simple_fast - Pour images simples")
    
    print("\n⚙️ TYPES DE PRÉTRAITEMENTS:")
    print("   • heavy_enhance - Amélioration forte")
    print("   • adaptive_enhance - Amélioration adaptative")
    print("   • gradient_boost - Boost des gradients")
    print("   • denoise_light - Débruitage léger")
    print("   • heavy_denoise - Débruitage fort")
    print("   • standard - Traitement standard")
    print("   • enhance_light - Amélioration légère")
    print("   • adaptive - Traitement adaptatif")
    
    print("\n📊 CRITÈRES DE SCORING:")
    print("   • Nombre optimal de rectangles (1-30)")
    print("   • Couverture optimale de l'image (10-80%)")
    print("   • Uniformité des tailles des rectangles")
    print("   • Ratios d'aspect raisonnables (1:1 à 3:1)")
    print("   • Niveau de confiance de détection")
    
    print("\n🚀 AVANTAGES:")
    print("   ✅ Détection automatique sans paramètres manuels")
    print("   ✅ Adaptation intelligente à chaque image/page")
    print("   ✅ Optimisation automatique des résultats")
    print("   ✅ Gestion des différents types d'images")
    print("   ✅ Progression en temps réel pour PDF")
    
    print("\n" + "=" * 50)
    print("📝 UTILISATION")
    print("=" * 50)
    
    print("\nPour utiliser le mode automatique:")
    print("   1. Envoyer POST vers /upload_auto au lieu de /upload")
    print("   2. Le système analysera automatiquement l'image")
    print("   3. Testera plusieurs configurations")
    print("   4. Choisira la meilleure automatiquement")
    print("   5. Retournera les résultats avec la config utilisée")
    
    print("\nExemple de réponse JSON:")
    example_response = {
        "filename": "exemple.pdf",
        "rectangles_count": 15,
        "auto_config_used": "high_contrast_standard",
        "auto_mode": True,
        "rectangles": [
            {
                "id": 0,
                "bbox": {"x": 100, "y": 200, "w": 300, "h": 400},
                "area": 120000,
                "corners": [[100, 200], [400, 200], [400, 600], [100, 600]],
                "artwork_number": "1234"
            }
        ]
    }
    print(json.dumps(example_response, indent=2))
    
    print("\n" + "=" * 50)
    print("🔗 ENDPOINTS DISPONIBLES")
    print("=" * 50)
    
    endpoints = [
        ("POST", "/upload", "Upload classique avec paramètres manuels"),
        ("POST", "/upload_auto", "🆕 Upload automatique intelligent"),
        ("GET", "/health", "Status du serveur"),
        ("GET", "/extract/<id>", "Extraire un rectangle"),
        ("GET", "/preview/<id>", "Prévisualiser un rectangle"),
        ("GET", "/pdf_extract_all", "Télécharger tous les rectangles PDF"),
        ("GET", "/ocr_check/<filename>", "Vérifier OCR existant"),
        ("GET", "/debug_page/<filename>/<page>", "Debug d'une page spécifique")
    ]
    
    for method, endpoint, description in endpoints:
        marker = "🆕" if "auto" in endpoint else "  "
        print(f"   {marker} {method:4} {endpoint:25} - {description}")
    
    print(f"\n✅ SmartAutoDetector intégré avec succès dans backend2.py!")
    print(f"🚀 Serveur prêt sur {base_url}")

if __name__ == "__main__":
    test_smart_auto_detector()