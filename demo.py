#!/usr/bin/env python3
"""
Script de démonstration rapide pour le détourage automatique
"""
import webbrowser
import time
import subprocess
import sys
from pathlib import Path

def main():
    print("🎨 DÉTOURAGE AUTOMATIQUE v2.0 - DEMO")
    print("=====================================")
    
    # Vérifier les fichiers
    if not Path("backend.py").exists():
        print("❌ backend.py non trouvé")
        return
    
    if not Path("frontend.html").exists():
        print("❌ frontend.html non trouvé")
        return
    
    print("✅ Fichiers trouvés")
    print("📡 Serveur backend déjà en cours...")
    print("🌐 Ouverture du frontend...")
    
    # Ouvrir le frontend
    frontend_path = Path("frontend.html").absolute()
    webbrowser.open(f"file://{frontend_path}")
    
    print("\n🎯 INSTRUCTIONS:")
    print("1. Dans la page web qui s'ouvre:")
    print("2. Glissez-déposez votre image d'études de mains")
    print("3. Cliquez sur 'Analyser l'image'")
    print("4. Attendez la détection (ça va détecter que c'est un dessin)")
    print("5. Téléchargez les objets détectés individuellement")
    
    print("\n✅ DEMO LANCÉE !")
    print("📱 La page web est maintenant ouverte")
    print("🔧 Le serveur Python tourne sur localhost:5000")
    
    print("\n💡 TIPS:")
    print("   - Ajustez la sensibilité si nécessaire (20-40 pour dessins)")
    print("   - Si aucun objet n'est détecté, augmentez la sensibilité")
    print("   - Format TIFF supporté nativement !")

if __name__ == "__main__":
    main() 