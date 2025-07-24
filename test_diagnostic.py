#!/usr/bin/env python3
"""
Script de diagnostic pour tester le fichier Pablo Picasso Vol31
"""

import os
import sys
import time
import PyPDF2
import pdfplumber
from pathlib import Path

def test_file_info():
    """Test 1: Informations sur le fichier"""
    print("🔍 TEST 1: Informations fichier")
    print("=" * 50)
    
    filepath = "uploads/PABLO-PICASSO-VOL31-1969-multi-page.pdf.ocr.pdf"
    
    if not os.path.exists(filepath):
        print("❌ Fichier non trouvé!")
        return False
    
    # Taille du fichier
    size_bytes = os.path.getsize(filepath)
    size_mb = size_bytes / (1024 * 1024)
    size_gb = size_mb / 1024
    
    print(f"📄 Fichier: {filepath}")
    print(f"📦 Taille: {size_gb:.2f} GB ({size_mb:.0f} MB)")
    
    return filepath

def test_pdf_pages(filepath):
    """Test 2: Compter les pages rapidement"""
    print("\n🔍 TEST 2: Comptage des pages")
    print("=" * 50)
    
    try:
        start_time = time.time()
        
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        elapsed = time.time() - start_time
        
        print(f"📄 Nombre de pages: {total_pages}")
        print(f"⏱️ Temps de comptage: {elapsed:.2f}s")
        
        return total_pages
        
    except Exception as e:
        print(f"❌ Erreur comptage: {e}")
        return None

def test_ocr_detection(filepath, total_pages):
    """Test 3: Détection OCR rapide"""
    print("\n🔍 TEST 3: Détection OCR")
    print("=" * 50)
    
    try:
        start_time = time.time()
        
        # Test PyPDF2 sur 3 premières pages
        text_pages_found = 0
        sample_pages = [0, 1, 2] if total_pages >= 3 else list(range(total_pages))
        
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for i in sample_pages:
                try:
                    print(f"🔍 Test page {i+1}...")
                    page = pdf_reader.pages[i]
                    text = page.extract_text().strip()
                    
                    print(f"📝 Page {i+1}: {len(text)} caractères")
                    
                    if len(text) > 50:
                        text_pages_found += 1
                        print(f"✅ Page {i+1}: Texte détecté!")
                        # Afficher un échantillon
                        print(f"📄 Extrait: {text[:100]}...")
                    else:
                        print(f"❌ Page {i+1}: Pas de texte significatif")
                        
                except Exception as e:
                    print(f"⚠️ Erreur page {i+1}: {e}")
        
        elapsed = time.time() - start_time
        
        # Estimation
        estimated_text_pages = int((text_pages_found / len(sample_pages)) * total_pages) if sample_pages else 0
        text_ratio = estimated_text_pages / total_pages if total_pages > 0 else 0
        
        print(f"\n📊 RÉSULTATS OCR:")
        print(f"   Pages testées: {len(sample_pages)}")
        print(f"   Pages avec texte: {text_pages_found}")
        print(f"   Estimation totale: {estimated_text_pages}/{total_pages} pages ({text_ratio:.1%})")
        print(f"   ⏱️ Temps d'analyse: {elapsed:.2f}s")
        
        has_ocr = text_ratio >= 0.1
        print(f"   🤖 OCR détecté: {'OUI' if has_ocr else 'NON'}")
        
        return has_ocr, text_ratio
        
    except Exception as e:
        print(f"❌ Erreur détection OCR: {e}")
        return False, 0

def test_single_page_conversion(filepath):
    """Test 4: Conversion d'une seule page"""
    print("\n🔍 TEST 4: Conversion page unique")
    print("=" * 50)
    
    try:
        from pdf2image import convert_from_path
        
        print("🔄 Test conversion page 1 en DPI 600...")
        start_time = time.time()
        
        # Convertir SEULEMENT la première page
        pages = convert_from_path(
            filepath, 
            dpi=600,
            first_page=1,
            last_page=1
        )
        
        elapsed = time.time() - start_time
        
        if pages:
            page = pages[0]
            print(f"✅ Conversion réussie!")
            print(f"📐 Dimensions: {page.width}x{page.height} pixels")
            print(f"⏱️ Temps conversion: {elapsed:.2f}s")
            print(f"📏 Taille estimée: {(page.width * page.height * 3) / (1024*1024):.1f} MB par page")
            
            return elapsed
        else:
            print("❌ Conversion échouée")
            return None
            
    except Exception as e:
        print(f"❌ Erreur conversion: {e}")
        return None

def estimate_total_time(pages, conversion_time_per_page):
    """Test 5: Estimation du temps total"""
    print("\n🔍 TEST 5: Estimation temps total")
    print("=" * 50)
    
    if not conversion_time_per_page:
        print("❌ Impossible d'estimer sans temps de conversion")
        return
    
    print(f"📄 Pages à traiter: {pages}")
    print(f"⏱️ Temps par page: {conversion_time_per_page:.2f}s")
    
    # Estimation conservative
    total_conversion = pages * conversion_time_per_page
    total_processing = pages * 3  # 3s de traitement IA par page
    total_time = total_conversion + total_processing
    
    print(f"\n📊 ESTIMATIONS:")
    print(f"   🔄 Conversion totale: {total_conversion/60:.1f} minutes")
    print(f"   🤖 Traitement IA: {total_processing/60:.1f} minutes") 
    print(f"   ⏱️ TEMPS TOTAL: {total_time/60:.1f} minutes ({total_time/3600:.1f}h)")
    
    if total_time > 3600:  # Plus d'1 heure
        print(f"\n⚠️ ALERTE: Traitement très long estimé!")
        print(f"💡 Recommandations:")
        print(f"   - Utiliser l'OCR existant si possible")
        print(f"   - Réduire la qualité (DPI 300 au lieu de 600)")
        print(f"   - Traiter un échantillon d'abord")

def main():
    """Fonction principale de diagnostic"""
    print("🚀 DIAGNOSTIC PABLO PICASSO VOL31")
    print("=" * 60)
    
    # Test 1: Info fichier
    filepath = test_file_info()
    if not filepath:
        return
    
    # Test 2: Comptage pages
    total_pages = test_pdf_pages(filepath)
    if not total_pages:
        return
    
    # Test 3: OCR
    has_ocr, text_ratio = test_ocr_detection(filepath, total_pages)
    
    # Test 4: Conversion
    conversion_time = test_single_page_conversion(filepath)
    
    # Test 5: Estimation
    if conversion_time:
        estimate_total_time(total_pages, conversion_time)
    
    # Recommandations finales
    print("\n🎯 RECOMMANDATIONS FINALES")
    print("=" * 50)
    
    if has_ocr and text_ratio > 0.5:
        print("✅ RECOMMANDATION: Utiliser l'OCR existant!")
        print("   ⚡ Temps: 5-10 secondes au lieu de plusieurs heures")
        print("   📄 Extraction directe du texte")
    else:
        print("⚠️ RECOMMANDATION: Traitement très long!")
        print("   ⏱️ Temps estimé: Plusieurs heures")
        print("   💡 Suggestions:")
        print("      - Testez sur quelques pages d'abord")
        print("      - Utilisez une qualité réduite")
        print("      - Préparez-vous à une longue attente")
    
    print(f"\n🎉 Diagnostic terminé!")

if __name__ == "__main__":
    main() 