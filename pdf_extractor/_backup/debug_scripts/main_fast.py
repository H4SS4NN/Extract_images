#!/usr/bin/env python3
"""
Version RAPIDE de l'extracteur PDF pour les vieux PC
"""
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from core import PDFExtractor
from utils import logger

def main_fast():
    """Fonction principale optimisée pour vieux PC"""
    print("🚀 EXTRACTEUR PDF RAPIDE - MODE VIEUX PC")
    print("=" * 70)
    print("⚡ Mode optimisé : Performance avant qualité")
    print("🔧 Timeouts réduits, moins de détecteurs")
    print("📱 Idéal pour PC lents ou cartes graphiques anciennes")
    print("🎯 Détection directe des numéros (pas de sommaire)")
    print("=" * 70)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Mode rapide : Collection Dubuffet par défaut (pas de sommaire)
    print("\n⚡ Mode RAPIDE activé:")
    print("   - Collection: Dubuffet (pas de recherche sommaire)")
    print("   - Détecteurs: Réduits")
    print("   - Timeouts: Courts")
    
    collection_choice = input("Forcer Picasso quand même ? (o/N): ").strip().lower()
    if collection_choice in ['o', 'oui', 'y', 'yes']:
        selected_collection = 'picasso'
        print("⚠️ Mode Picasso : La recherche sommaire sera limitée")
    else:
        selected_collection = 'dubuffet'
        print("✅ Mode Dubuffet : Pas de recherche sommaire")
    
    # Demander un nombre de pages limité
    max_pages_input = input("📄 Nombre MAX de pages (5 recommandé): ").strip()
    max_pages = 5  # Par défaut
    if max_pages_input and max_pages_input.isdigit():
        max_pages = min(int(max_pages_input), 10)  # Max 10 pages
    
    start_page_input = input("🔢 Page de départ (1 par défaut): ").strip()
    start_page = 1
    if start_page_input and start_page_input.isdigit():
        start_page = int(start_page_input)
    
    # Créer l'extracteur avec optimisations
    print(f"\n🔧 Configuration pour PC lent:")
    print(f"   - Collection: {selected_collection.title()}")
    print(f"   - Pages: {start_page} à {start_page + max_pages - 1}")
    print(f"   - Timeouts OCR: 5s (au lieu de 15s)")
    
    # Créer l'extracteur avec désactivation du sommaire pour la performance
    skip_toc = True  # Toujours désactiver en mode rapide
    extractor = PDFExtractor(collection_name=selected_collection, skip_toc_search=skip_toc)
    
    # Réduire les détecteurs pour la performance
    print("   - Détecteurs: UltraDetector seulement")
    extractor.detectors = extractor.detectors[:1]  # Garder seulement UltraDetector
    
    # Lancer l'extraction
    print("\n🚀 Extraction RAPIDE en cours...")
    print("⚡ Mode performance : peut manquer quelques images mais plus rapide")
    
    import time
    start_time = time.time()
    
    success = extractor.extract_pdf(pdf_path, max_pages, start_page)
    
    elapsed_time = time.time() - start_time
    
    if success:
        print(f"\n✅ Extraction RAPIDE terminée en {elapsed_time:.1f}s!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("⚡ Mode rapide: Qualité réduite mais adapté aux vieux PC")
    else:
        print(f"\n❌ Extraction échouée après {elapsed_time:.1f}s")

if __name__ == "__main__":
    main_fast()
