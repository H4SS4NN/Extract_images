#!/usr/bin/env python3
"""
Test rapide de la détection améliorée des rectangles
"""

from extract_pdf_ultra_sensible import UltraSensitivePDFExtractor
import os

def test_single_page():
    """Test sur une page spécifique"""
    pdf_path = "uploads/PABLO-PICASSO-VOL20-1961-1962.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ Fichier non trouvé: {pdf_path}")
        return
    
    print("🚀 TEST DÉTECTION AMÉLIORÉE")
    print("=" * 50)
    print("🎯 Focus: Détection des rectangles (OCR désactivé)")
    print("✨ Seuils plus permissifs pour images claires")
    print("☀️ Détection spéciale pour images très claires")
    print("=" * 50)
    
    # Créer l'extracteur
    extractor = UltraSensitivePDFExtractor()
    
    # Tester sur la page 6 (qui avait des problèmes)
    print(f"\n📄 Test sur la page 6...")
    success = extractor.extract_pdf(pdf_path, max_pages=1, start_page=6)
    
    if success:
        print("\n✅ Test terminé!")
        print(f"📁 Résultats: {extractor.session_dir}")
    else:
        print("\n❌ Test échoué!")

if __name__ == "__main__":
    test_single_page()
