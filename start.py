#!/usr/bin/env python3
"""
Script de démarrage pour le système de détourage automatique
"""

import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path

def install_requirements():
    """Installer les dépendances si nécessaire"""
    print("🔧 Vérification des dépendances...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dépendances installées")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur installation dépendances: {e}")
        return False
    return True

def start_backend():
    """Démarrer le serveur Flask"""
    print("🚀 Démarrage du serveur backend...")
    try:
        # Lancer le serveur en arrière-plan
        process = subprocess.Popen([sys.executable, "backend.py"])
        
        # Attendre que le serveur démarre
        print("⏳ Attente du démarrage du serveur...")
        time.sleep(3)
        
        return process
    except Exception as e:
        print(f"❌ Erreur démarrage serveur: {e}")
        return None

def open_frontend():
    """Ouvrir le frontend dans le navigateur"""
    frontend_path = Path("frontend.html").absolute()
    if frontend_path.exists():
        print("🌐 Ouverture du frontend...")
        webbrowser.open(f"file://{frontend_path}")
        return True
    else:
        print("❌ Fichier frontend.html non trouvé")
        return False

def main():
    print("=" * 60)
    print("🎨 SYSTÈME DE DÉTOURAGE AUTOMATIQUE v2.0")
    print("🐍 Backend Python + OpenCV")
    print("=" * 60)
    
    # Vérifier que nous sommes dans le bon dossier
    if not Path("backend.py").exists():
        print("❌ Erreur: backend.py non trouvé dans ce dossier")
        print("   Lancez ce script depuis le dossier du projet")
        return
    
    # Installer les dépendances
    if not install_requirements():
        return
    
    # Démarrer le backend
    server_process = start_backend()
    if not server_process:
        return
    
    # Ouvrir le frontend
    time.sleep(2)
    if open_frontend():
        print("\n✅ Système démarré avec succès !")
        print("📡 Backend: http://localhost:5000")
        print("🌐 Frontend: ouvert dans le navigateur")
        print("\n🎯 Instructions:")
        print("   1. Glissez-déposez une image sur la zone de upload")
        print("   2. Ajustez la sensibilité si nécessaire")
        print("   3. Cliquez sur 'Analyser l'image'")
        print("   4. Téléchargez les objets détectés")
        print("\n💡 Fermer cette fenêtre arrêtera le serveur")
        
        try:
            # Attendre que l'utilisateur ferme le script
            input("\n📋 Appuyez sur Entrée pour arrêter le serveur...")
        except KeyboardInterrupt:
            pass
        finally:
            print("\n🛑 Arrêt du serveur...")
            server_process.terminate()
            server_process.wait()
            print("✅ Serveur arrêté")
    else:
        server_process.terminate()

if __name__ == "__main__":
    main() 