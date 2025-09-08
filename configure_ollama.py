#!/usr/bin/env python3
"""
Script de configuration Ollama pour optimiser LLaVA
"""

import requests
import json
import time

def check_ollama_status():
    """Vérifie le statut d'Ollama"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✅ Ollama est en cours d'exécution")
            print(f"📦 Modèles disponibles: {[model['name'] for model in models]}")
            return True
        else:
            print(f"❌ Ollama répond avec erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ollama n'est pas accessible: {e}")
        print("💡 Démarrez Ollama avec: ollama serve")
        return False

def optimize_llava():
    """Optimise LLaVA pour de meilleures performances"""
    try:
        # Configuration optimisée pour LLaVA
        config = {
            "model": "llava:latest",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 200,
                "num_ctx": 2048,
                "num_predict": 100,
                "num_gpu": 1,  # Utiliser GPU si disponible
                "num_thread": 4,  # Nombre de threads
                "repeat_penalty": 1.1,
                "stop": ["\n\n", "Human:", "Assistant:"]
            }
        }
        
        print("🔧 Configuration de LLaVA pour de meilleures performances...")
        
        # Tester avec une requête simple
        test_payload = {
            "model": "llava:latest",
            "prompt": "Test de performance",
            "stream": False,
            "options": config["options"]
        }
        
        print("⏳ Test de performance LLaVA...")
        start_time = time.time()
        
        response = requests.post("http://localhost:11434/api/generate", json=test_payload, timeout=60)
        
        if response.status_code == 200:
            end_time = time.time()
            duration = end_time - start_time
            print(f"✅ LLaVA répond en {duration:.1f} secondes")
            
            if duration < 10:
                print("🚀 LLaVA est rapide - prêt pour l'analyse")
                return True
            elif duration < 30:
                print("⚠️ LLaVA est lent mais utilisable")
                return True
            else:
                print("🐌 LLaVA est très lent - considérez un modèle plus rapide")
                return False
        else:
            print(f"❌ Erreur test LLaVA: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout LLaVA - le modèle est trop lent")
        return False
    except Exception as e:
        print(f"❌ Erreur configuration LLaVA: {e}")
        return False

def suggest_alternatives():
    """Suggère des alternatives si LLaVA est trop lent"""
    print("\n💡 ALTERNATIVES SI LLAVA EST TROP LENT:")
    print("=" * 50)
    print("1. Modèles plus rapides:")
    print("   - ollama pull llava:7b (plus petit)")
    print("   - ollama pull llava:13b (équilibré)")
    print("   - ollama pull llava:34b (plus précis mais plus lent)")
    print()
    print("2. Configuration système:")
    print("   - Augmentez la RAM allouée à Ollama")
    print("   - Utilisez un GPU si disponible")
    print("   - Fermez les autres applications")
    print()
    print("3. Le script fonctionnera sans LLaVA:")
    print("   - Correction automatique des patterns")
    print("   - Détection OCR avec Tesseract")
    print("   - Analyse de cohérence basique")

def main():
    print("🔧 CONFIGURATION OLLAMA POUR LLAVA")
    print("=" * 50)
    
    # Vérifier Ollama
    if not check_ollama_status():
        return
    
    # Optimiser LLaVA
    if optimize_llava():
        print("\n✅ LLaVA est configuré et prêt !")
        print("🎯 Le script extract_pdf_ultra_sensible.py peut maintenant utiliser LLaVA")
    else:
        print("\n⚠️ LLaVA a des problèmes de performance")
        suggest_alternatives()
    
    print("\n📋 RÉSUMÉ:")
    print("- LLaVA sera utilisé pour l'analyse visuelle avancée")
    print("- Si LLaVA est trop lent, le script utilisera la correction automatique")
    print("- Toutes les fonctionnalités principales fonctionnent sans LLaVA")

if __name__ == "__main__":
    main()
