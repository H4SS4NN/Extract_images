#!/usr/bin/env python3
"""
Script de compatibilité - Utilise la nouvelle architecture modulaire
"""

import sys
from pathlib import Path

# Ajouter le répertoire pdf_extractor au path
pdf_extractor_path = Path(__file__).parent / "pdf_extractor"
sys.path.insert(0, str(pdf_extractor_path))

from core import PDFExtractor
from utils import logger

def main():
    """Fonction principale - Compatible avec l'ancien script"""
    print("🚀 EXTRACTEUR PDF ULTRA SENSIBLE v2.0")
    print("=" * 60)
    print("🎯 MODE ULTRA : CAPTURE VRAIMENT TOUT !")
    print("✨ Architecture modulaire - Code maintenable")
    print("🔬 Multi-détection, seuils ultra-bas, DPI élevé")
    print("☁️ Spécialisé pour fonds clairs et balance des blancs")
    print("🎨 Détection par saturation et contours doux")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Intégration Ollama pour correction automatique")
    print("=" * 60)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Demander la page de départ (optionnel)
    start_page_input = input("🔢 Page de départ (1 par défaut): ").strip()
    start_page = 1
    if start_page_input and start_page_input.isdigit():
        start_page = int(start_page_input)
    
    # Demander le nombre de pages (optionnel)
    max_pages_input = input("📄 Nombre max de pages (Entrée = jusqu'à la fin): ").strip()
    max_pages = None
    if max_pages_input and max_pages_input.isdigit():
        max_pages = int(max_pages_input)
    
    # Créer l'extracteur ULTRA
    extractor = PDFExtractor()
    
    # Lancer l'extraction ULTRA
    print("\n🚀 Extraction ULTRA en cours...")
    print("⚡ Chaque page testée avec 8+ méthodes différentes")
    print("🔬 Seuils ultra-permissifs, DPI élevé")
    print("☁️ Optimisé pour fonds clairs et balance des blancs")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Correction automatique avec Ollama si disponible")
    
    success = extractor.extract_pdf(pdf_path, max_pages, start_page)
    
    if success:
        print("\n✅ Extraction ULTRA terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Mode ULTRA: Toutes les images devraient être capturées !")
    else:
        print("\n❌ Extraction ULTRA échouée!")

if __name__ == "__main__":
    main()
