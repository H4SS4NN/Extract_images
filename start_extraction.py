#!/usr/bin/env python3
"""
Script de démarrage rapide pour l'extraction PDF ULTRA SENSIBLE
Gère automatiquement la configuration LLaVA et lance l'extraction
"""

import subprocess
import sys
import os
import time

def check_dependencies():
    """Vérifie les dépendances"""
    print("🔍 Vérification des dépendances...")
    
    # Vérifier Python
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ requis")
        return False
    
    # Vérifier les modules
    try:
        import cv2
        import numpy as np
        import requests
        print("✅ Modules Python OK")
    except ImportError as e:
        print(f"❌ Module manquant: {e}")
        print("💡 Installez avec: pip install opencv-python numpy requests")
        return False
    
    return True

def check_ollama():
    """Vérifie Ollama"""
    print("🔍 Vérification d'Ollama...")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            llava_models = [m['name'] for m in models if 'llava' in m['name'].lower()]
            
            if llava_models:
                print(f"✅ Ollama + LLaVA disponible: {llava_models[0]}")
                return True
            else:
                print("⚠️ Ollama disponible mais LLaVA non installé")
                print("💡 Installez LLaVA avec: ollama pull llava")
                return False
        else:
            print("❌ Ollama non accessible")
            return False
    except:
        print("❌ Ollama non installé ou non démarré")
        print("💡 Installez Ollama: https://ollama.ai/")
        return False

def start_ollama():
    """Démarre Ollama si possible"""
    print("🚀 Tentative de démarrage d'Ollama...")
    
    try:
        # Essayer de démarrer Ollama en arrière-plan
        subprocess.Popen(["ollama", "serve"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        time.sleep(3)  # Attendre que Ollama démarre
        
        # Vérifier si ça marche
        if check_ollama():
            print("✅ Ollama démarré avec succès")
            return True
        else:
            print("⚠️ Ollama n'a pas démarré automatiquement")
            return False
    except:
        print("⚠️ Impossible de démarrer Ollama automatiquement")
        print("💡 Démarrez manuellement avec: ollama serve")
        return False

def run_extraction():
    """Lance l'extraction PDF"""
    print("\n🚀 LANCEMENT DE L'EXTRACTION PDF ULTRA SENSIBLE")
    print("=" * 60)
    
    try:
        # Importer et lancer le script principal
        from extract_pdf_ultra_sensible import main
        main()
    except Exception as e:
        print(f"❌ Erreur lors du lancement: {e}")
        return False
    
    return True

def main():
    print("🎯 EXTRACTEUR PDF ULTRA SENSIBLE - DÉMARRAGE RAPIDE")
    print("=" * 60)
    
    # Vérifier les dépendances
    if not check_dependencies():
        print("\n❌ Dépendances manquantes - installation requise")
        return
    
    # Vérifier Ollama
    ollama_ok = check_ollama()
    if not ollama_ok:
        print("\n⚠️ Ollama/LLaVA non disponible")
        print("💡 Le script fonctionnera sans LLaVA (correction automatique uniquement)")
        
        # Essayer de démarrer Ollama
        if not start_ollama():
            print("⚠️ Continuation sans LLaVA...")
    
    # Lancer l'extraction
    print("\n" + "="*60)
    if run_extraction():
        print("\n✅ Extraction terminée avec succès !")
    else:
        print("\n❌ Erreur lors de l'extraction")

if __name__ == "__main__":
    main()
