#!/usr/bin/env python3
"""
Script de test pour vérifier que LLaVA fonctionne correctement
"""

import requests
import json
import cv2
import numpy as np
import base64

def test_ollama_connection():
    """Teste la connexion à Ollama"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            print(f"✅ Ollama connecté - Modèles disponibles: {model_names}")
            
            # Chercher LLaVA
            llava_models = [name for name in model_names if 'llava' in name.lower()]
            if llava_models:
                print(f"✅ LLaVA trouvé: {llava_models}")
                return llava_models[0]
            else:
                print("❌ LLaVA non trouvé")
                print("💡 Pour installer LLaVA: ollama pull llava")
                return None
        else:
            print(f"❌ Erreur Ollama: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur connexion Ollama: {e}")
        print("💡 Pour installer Ollama: https://ollama.ai/")
        return None

def test_llava_vision(model_name):
    """Teste les capacités visuelles de LLaVA"""
    try:
        # Créer une image de test plus simple
        test_image = np.ones((200, 400, 3), dtype=np.uint8) * 255  # Image blanche
        cv2.putText(test_image, "123", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        
        # Convertir en base64
        _, buffer = cv2.imencode('.jpg', test_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Prompt très simple pour éviter les timeouts
        prompt = "Quels nombres vois-tu dans cette image ? Réponds juste les nombres séparés par des virgules."
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "max_tokens": 50,  # Très court
                "num_ctx": 1024,   # Contexte minimal
                "num_predict": 30  # Très limité
            }
        }
        
        print("🧪 Test des capacités visuelles LLaVA...")
        print("⏳ LLaVA peut être lent, veuillez patienter...")
        
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            print(f"🤖 Réponse LLaVA: {response_text}")
            
            # Vérifier si LLaVA voit le nombre 123
            if '123' in response_text:
                print("✅ LLaVA fonctionne correctement - vision activée")
                print("🎯 LLaVA peut détecter les numéros d'œuvres")
                return True
            else:
                print("⚠️ LLaVA répond mais ne voit pas le nombre 123")
                print("💡 LLaVA peut avoir des limitations de vision")
                return False
        else:
            print(f"❌ Erreur requête LLaVA: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout LLaVA - le modèle est trop lent")
        print("💡 Essayez de redémarrer Ollama ou utilisez un modèle plus rapide")
        return False
    except Exception as e:
        print(f"❌ Erreur test LLaVA: {e}")
        return False

def main():
    print("🧪 TEST LLAVA - Vérification des capacités")
    print("=" * 50)
    
    # Test 1: Connexion Ollama
    model_name = test_ollama_connection()
    if not model_name:
        return
    
    # Test 2: Capacités visuelles
    if test_llava_vision(model_name):
        print("\n✅ LLaVA est prêt pour l'analyse des catalogues d'art !")
        print("🎯 Le script extract_pdf_ultra_sensible.py peut maintenant utiliser LLaVA")
    else:
        print("\n❌ LLaVA a des problèmes - vérifiez l'installation")

if __name__ == "__main__":
    main()
