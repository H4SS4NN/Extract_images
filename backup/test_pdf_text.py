#!/usr/bin/env python3
import pdfplumber

pdf_path = '../uploads/PABLO PICASSO/PABLO-PICASSO-VOL31-1969-multi-page.pdf.ocr_1.pdf'

try:
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f'📄 Total pages: {total_pages}')
        
        # Tester les 5 dernières pages
        for i in range(max(0, total_pages-5), total_pages):
            page = pdf.pages[i]
            text = page.extract_text()
            text_len = len(text) if text else 0
            sample = text[:100] if text else 'AUCUN TEXTE'
            print(f'Page {i+1}: {text_len} caractères - Échantillon: {sample}')
            
        # Tester spécifiquement les pages 187-195 (sommaire connu)
        print("\n🔍 Test pages sommaire (187-195):")
        for i in range(186, min(195, total_pages)):  # Pages 187-195 (index 186-194)
            page = pdf.pages[i]
            text = page.extract_text()
            text_len = len(text) if text else 0
            sample = text[:200] if text else 'AUCUN TEXTE'
            print(f'Page {i+1}: {text_len} caractères')
            if text_len > 0:
                print(f'  Échantillon: {sample}')
                # Chercher des mots-clés du sommaire
                keywords = ['planches', 'sommaire', 'table', 'tête', 'homme']
                found_keywords = [kw for kw in keywords if kw.lower() in text.lower()]
                if found_keywords:
                    print(f'  🎯 Mots-clés trouvés: {found_keywords}')
            print()
            
except Exception as e:
    print(f'Erreur: {e}')
