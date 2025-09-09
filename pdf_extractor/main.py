"""
Point d'entrée principal pour l'extracteur PDF
"""
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from core import PDFExtractor
from utils import logger

def main():
    """Fonction principale"""
    print("🚀 EXTRACTEUR PDF ULTRA SENSIBLE")
    print("=" * 60)
    print("🎯 MODE ULTRA : CAPTURE VRAIMENT TOUT !")
    print("✨ Multi-détection, seuils ultra-bas, DPI élevé")
    print("🔬 8+ algorithmes par page, fusion intelligente")
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
