#!/usr/bin/env python3
"""
Script d'installation de Mistral local via Ollama
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

def check_ollama_installed():
    """Vérifie si Ollama est installé"""
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Ollama installé: {result.stdout.strip()}")
            return True
        else:
            print("❌ Ollama non installé")
            return False
    except FileNotFoundError:
        print("❌ Ollama non trouvé dans le PATH")
        return False

def check_ollama_running():
    """Vérifie si Ollama est en cours d'exécution"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama est en cours d'exécution")
            return True
        else:
            print("❌ Ollama n'est pas en cours d'exécution")
            return False
    except:
        print("❌ Ollama n'est pas accessible")
        return False

def start_ollama():
    """Démarre Ollama en arrière-plan"""
    print("🚀 Démarrage d'Ollama...")
    try:
        # Démarrer Ollama en arrière-plan
        subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Attendre que Ollama démarre
        print("⏳ Attente du démarrage d'Ollama...")
        for i in range(30):  # Attendre jusqu'à 30 secondes
            time.sleep(1)
            if check_ollama_running():
                print("✅ Ollama démarré avec succès")
                return True
            print(f"   Tentative {i+1}/30...")
        
        print("❌ Timeout: Ollama n'a pas démarré dans les temps")
        return False
    except Exception as e:
        print(f"❌ Erreur démarrage Ollama: {e}")
        return False

def install_mistral():
    """Installe le modèle Mistral"""
    print("📥 Installation de Mistral...")
    try:
        # Installer Mistral (version 7B pour commencer)
        result = subprocess.run(['ollama', 'pull', 'mistral:7b'], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Mistral installé avec succès")
            return True
        else:
            print(f"❌ Erreur installation Mistral: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout: L'installation de Mistral prend trop de temps")
        return False
    except Exception as e:
        print(f"❌ Erreur installation Mistral: {e}")
        return False

def test_mistral():
    """Teste Mistral avec un prompt simple"""
    print("🧪 Test de Mistral...")
    try:
        import requests
        
        payload = {
            "model": "mistral:7b",
            "prompt": "Bonjour, peux-tu me dire 'Hello World' en JSON?",
            "stream": False
        }
        
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Mistral fonctionne correctement")
            print(f"   Réponse: {result.get('response', '')[:100]}...")
            return True
        else:
            print(f"❌ Erreur test Mistral: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test Mistral: {e}")
        return False

def main():
    """Fonction principale d'installation"""
    print("🔧 INSTALLATION MISTRAL LOCAL VIA OLLAMA")
    print("=" * 50)
    
    # Vérifier si Ollama est installé
    if not check_ollama_installed():
        print("\n📋 Pour installer Ollama:")
        print("   1. Allez sur https://ollama.ai/")
        print("   2. Téléchargez et installez Ollama")
        print("   3. Relancez ce script")
        return False
    
    # Vérifier si Ollama est en cours d'exécution
    if not check_ollama_running():
        if not start_ollama():
            print("\n❌ Impossible de démarrer Ollama")
            print("💡 Essayez de démarrer Ollama manuellement: ollama serve")
            return False
    
    # Installer Mistral
    if not install_mistral():
        print("\n❌ Installation de Mistral échouée")
        return False
    
    # Tester Mistral
    if not test_mistral():
        print("\n❌ Test de Mistral échoué")
        return False
    
    print("\n🎉 INSTALLATION TERMINÉE AVEC SUCCÈS!")
    print("=" * 50)
    print("✅ Ollama est en cours d'exécution")
    print("✅ Mistral est installé et fonctionnel")
    print("\n🚀 Vous pouvez maintenant utiliser l'analyseur de sommaires!")
    print("   python pdf_extractor/demo_summary.py")
    print("   python pdf_extractor/setup_mistral.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

