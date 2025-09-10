#!/usr/bin/env python3
"""
Test en mode rapide pour vieux PC
"""

import sys
import logging
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from core import PDFExtractor
from utils import logger

def test_quick_extraction():
    """Test d'extraction rapide avec logs de debug"""
    print("🧪 TEST MODE RAPIDE - VIEUX PC")
    print("=" * 50)
    
    # Activer les logs de debug
    logger.logger.setLevel(logging.DEBUG)
    
    # Créer extracteur Picasso
    extractor = PDFExtractor('picasso')
    
    # Test avec un PDF réel mais seulement 2 pages
    pdf_path = input("📁 Chemin du PDF (ou Entrée pour test fictif): ").strip()
    
    if not pdf_path:
        # Test avec fichier fictif pour voir les logs de sommaire
        from toc_planches import extract_toc_from_pdf_multipage
        keywords = ['sommaire', 'table des matières', 'planches']
        print(f"\n🔍 Test détection sommaire avec mots-clés: {keywords}")
        result = extract_toc_from_pdf_multipage("fichier_inexistant.pdf", last_n=5, keywords=keywords)
        print(f"📊 Résultat: {result}")
    else:
        # Test d'extraction réelle mais limitée
        print(f"\n🚀 Extraction rapide de {pdf_path}")
        print("⚡ Mode optimisé pour vieux PC - timeouts réduits")
        
        success = extractor.extract_pdf(pdf_path, max_pages=3, start_page=1)  # Seulement 3 pages
        
        if success:
            print(f"✅ Extraction terminée: {extractor.session_dir}")
        else:
            print("❌ Extraction échouée")
    
    print("\n✅ Test terminé!")


if __name__ == "__main__":
    test_quick_extraction()
