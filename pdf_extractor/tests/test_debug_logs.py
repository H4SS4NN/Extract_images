#!/usr/bin/env python3
"""
Test des logs de debug pour la détection de sommaire
"""

import sys
import logging
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from core import PDFExtractor
from utils import logger

def test_debug_logs():
    """Test avec logs de debug activés"""
    print("🧪 TEST LOGS DEBUG SOMMAIRE")
    print("=" * 50)
    
    # Activer tous les logs de debug
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
    logger.setLevel(logging.DEBUG)
    
    # Créer un extracteur Picasso
    print("\n📚 Création extracteur Picasso...")
    extractor = PDFExtractor('picasso')
    
    # Test avec un fichier fictif pour voir les logs
    fake_pdf = "test_inexistant.pdf"
    print(f"\n🔍 Test avec fichier fictif: {fake_pdf}")
    
    # Cela va déclencher les logs d'erreur
    from toc_planches import extract_toc_from_pdf_multipage
    
    keywords = ['sommaire', 'table des matières', 'planches']
    print(f"📋 Mots-clés: {keywords}")
    
    result = extract_toc_from_pdf_multipage(fake_pdf, last_n=5, keywords=keywords)
    print(f"📊 Résultat: {result}")
    
    print("\n✅ Test terminé!")


if __name__ == "__main__":
    test_debug_logs()
