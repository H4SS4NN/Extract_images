#!/usr/bin/env python3
"""
Script pour débugger une page spécifique du PDF Pablo Picasso
"""

import requests
import json

def test_page(page_number, sensitivity=50, mode='high_contrast', dpi=300):
    """Test une page spécifique"""
    print(f"🔍 TEST PAGE {page_number}")
    print("=" * 50)
    
    url = f"http://localhost:5000/debug_page/PABLO-PICASSO-VOL31-1969-multi-page.pdf.ocr.pdf/{page_number}"
    params = {
        'sensitivity': sensitivity,
        'mode': mode,
        'dpi': dpi
    }
    
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Page {page_number} analysée avec succès!")
            
            # **NOUVELLE SECTION: Analyse physique de la page**
            page_analysis = data['page_analysis']
            print(f"\n📏 ANALYSE PHYSIQUE DE LA PAGE:")
            print(f"   - Format: {page_analysis['page_format']}")
            print(f"   - Taille physique: {page_analysis['physical_size']}")
            print(f"   - Aire: {page_analysis['area_mm2']:,.0f} mm²")
            print(f"   - DPI recommandé: {page_analysis['recommended_dpi']}")
            print(f"   - DPI utilisé: {page_analysis['dpi_actually_used']} ({page_analysis['optimal_vs_used']})")
            
            print(f"\n📐 RÉSOLUTION FINALE:")
            print(f"   - Taille image: {data['image_size']} ({data['image_megapixels']} MP)")
            print(f"   - Temps traitement: {data['processing_time']}s")
            print(f"   - Rectangles trouvés: {data['rectangles_found']}")
            
            # **NOUVELLE SECTION: Paramètres adaptatifs**
            detection = data['detection_params']
            debug = data['debug_info']
            print(f"\n🎯 PARAMÈTRES ADAPTATIFS:")
            print(f"   - Seuil aire minimale: {debug['adaptive_min_area']:,} pixels")
            print(f"   - Limite rectangles: {debug['adaptive_max_rectangles']}")
            print(f"   - Cache utilisé: {'Oui' if debug['analysis_cache_hit'] else 'Non'}")
            print(f"   - MP estimés: {detection['estimated_megapixels']} MP")
            
            if data['rectangles_found'] > 0:
                print(f"\n📋 Rectangles détectés:")
                for i, rect in enumerate(data['rectangles'][:5]):  # Max 5 pour lisibilité
                    bbox = rect['bbox']
                    area_percent = (rect['area'] / debug['adaptive_min_area']) * 100
                    print(f"   {i+1}. {bbox['w']}×{bbox['h']} px (aire: {rect['area']:.0f}, {area_percent:.0f}% du seuil)")
                
                if data['rectangles_found'] > 5:
                    print(f"   ... et {data['rectangles_found'] - 5} autres")
            
            return data
            
        else:
            error_data = response.json()
            print(f"❌ Erreur: {error_data.get('error', 'Erreur inconnue')}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au serveur (localhost:5000)")
        print("💡 Assurez-vous que le serveur backend est démarré avec: python backend.py")
        return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_multiple_pages():
    """Test plusieurs pages avec différents paramètres"""
    print("🚀 TEST MULTI-PAGES")
    print("=" * 60)
    
    # Pages à tester (début, milieu, fin)
    test_pages = [1, 2, 50, 100, 150, 196]
    
    for page in test_pages:
        print(f"\n📄 Test page {page}...")
        result = test_page(page, sensitivity=50, mode='high_contrast', dpi=300)
        
        if result:
            rectangles = result['rectangles_found']
            time_taken = result['processing_time']
            megapixels = result['image_megapixels']
            
            print(f"   → {rectangles} rectangles en {time_taken}s ({megapixels}MP)")
        else:
            print(f"   → ÉCHEC")
        
        print("-" * 30)

def test_sensitivity_comparison():
    """Compare différents niveaux de sensibilité sur la même page"""
    print("🎛️ TEST SENSIBILITÉ")
    print("=" * 60)
    
    page = 10  # Page test
    sensitivities = [25, 50, 75]
    
    print(f"📄 Test page {page} avec différentes sensibilités:")
    
    for sens in sensitivities:
        result = test_page(page, sensitivity=sens, mode='high_contrast', dpi=300)
        if result:
            print(f"   Sensibilité {sens}: {result['rectangles_found']} rectangles")
        else:
            print(f"   Sensibilité {sens}: ÉCHEC")

def test_visual_debug(page_number, mode='high_contrast', sensitivity=50, dpi=300):
    """Test avec debug visuel - télécharge un ZIP d'images intermédiaires"""
    print(f"🎨 DEBUG VISUEL PAGE {page_number}")
    print("=" * 60)
    
    url = f"http://localhost:5000/debug_visual/PABLO-PICASSO-VOL31-1969-multi-page.pdf.ocr.pdf/{page_number}"
    params = {
        'sensitivity': sensitivity,
        'mode': mode,
        'dpi': dpi
    }
    
    try:
        print(f"📥 Téléchargement des images de debug...")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            # Sauvegarder le ZIP
            filename = f"debug_visual_page_{page_number}_{mode}.zip"
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Images de debug sauvegardées: {filename}")
            print(f"📁 Le ZIP contient:")
            print(f"   - 10 images de toutes les étapes de traitement")
            print(f"   - Fichier de statistiques détaillées")
            print(f"   - Conseils pour résoudre les problèmes")
            print(f"\n💡 Ouvrez les images pour voir exactement ce qui se passe!")
            
            return filename
            
        else:
            error_data = response.json()
            print(f"❌ Erreur: {error_data.get('error', 'Erreur inconnue')}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au serveur (localhost:5000)")
        return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_problematic_pages():
    """Test spécifique pour les pages qui posent problème"""
    print("🚨 TEST PAGES PROBLÉMATIQUES")
    print("=" * 60)
    
    # Pages spécifiquement identifiées par l'utilisateur
    problematic_pages = [163, 258]  # Pages avec bugs confirmés
    
    print("📄 Test des pages avec bugs identifiés par l'utilisateur...")
    print("   - Page 163: 0 rectangles sur web mais détectés en debug")
    print("   - Page 258: Plusieurs rectangles visibles mais 1 seul détecté")
    
    print("📄 Test de pages potentiellement problématiques...")
    results = []
    
    for page in problematic_pages:
        print(f"\n🔍 Test page {page}...")
        result = test_page(page, sensitivity=50, mode='high_contrast', dpi=300)
        
        if result:
            rectangles = result['rectangles_found']
            if rectangles == 0:
                print(f"   ⚠️ PAGE PROBLÉMATIQUE: Aucun rectangle détecté")
                results.append({
                    'page': page,
                    'rectangles': rectangles,
                    'status': 'PROBLÉMATIQUE',
                    'analysis': result['page_analysis']
                })
            else:
                print(f"   ✅ OK: {rectangles} rectangles")
                results.append({
                    'page': page,
                    'rectangles': rectangles,
                    'status': 'OK'
                })
        else:
            print(f"   ❌ ÉCHEC: Impossible d'analyser")
            results.append({
                'page': page,
                'rectangles': 0,
                'status': 'ÉCHEC'
            })
    
    # Résumé
    print(f"\n📊 RÉSUMÉ:")
    problematic = [r for r in results if r['status'] == 'PROBLÉMATIQUE']
    ok_pages = [r for r in results if r['status'] == 'OK']
    failed = [r for r in results if r['status'] == 'ÉCHEC']
    
    print(f"   ✅ Pages OK: {len(ok_pages)}")
    print(f"   ⚠️ Pages problématiques: {len(problematic)}")
    print(f"   ❌ Pages en échec: {len(failed)}")
    
    if problematic:
        print(f"\n🚨 PAGES À INVESTIGUER:")
        for p in problematic:
            format_info = p.get('analysis', {}).get('page_format', 'Inconnu')
            print(f"   - Page {p['page']}: Format {format_info}")
        
        # Proposer debug visuel pour la première page problématique
        first_problematic = problematic[0]['page']
        print(f"\n💡 SUGGESTION: Debug visuel de la page {first_problematic}")
        print(f"   → test_visual_debug({first_problematic})")
    
    return results

def test_missing_rectangles_debug(page_number):
    """Test spécialisé pour comprendre pourquoi des rectangles sont manqués"""
    print(f"🔍 DEBUG RECTANGLES MANQUÉS - PAGE {page_number}")
    print("=" * 60)
    
    url = f"http://localhost:5000/debug_missing_rectangles/PABLO-PICASSO-VOL31-1969-multi-page.pdf.ocr.pdf/{page_number}"
    
    try:
        print(f"🧪 Test de 7 configurations différentes...")
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Analyse terminée pour page {page_number}")
            print(f"📊 Configurations testées: {data['total_configs_tested']}")
            
            best = data['best_result']
            if best:
                print(f"\n🏆 MEILLEURE CONFIGURATION:")
                config = best['config']
                print(f"   - Mode: {config['mode']}")
                print(f"   - Sensibilité: {config['sensitivity']}")
                print(f"   - DPI: {config['dpi']}")
                print(f"   - Rectangles trouvés: {best['rectangles_found']}")
                print(f"   - Seuil réduit: {best['seuil_reduit']:,} pixels")
                print(f"   - Seuil original: {best['seuil_original']:,} pixels")
                print(f"   - Taille image: {best['image_info']['size']}")
                
                recommendations = data['recommendations']
                print(f"\n💡 DIAGNOSTIC:")
                print(f"   - Problème: {recommendations['problem_analysis']}")
                print(f"   - Max rectangles possible: {recommendations['max_rectangles_found']}")
            
            print(f"\n📋 TOUS LES RÉSULTATS:")
            for i, result in enumerate(data['all_results'][:5]):  # Top 5
                config = result['config']
                print(f"   {i+1}. {result['rectangles_found']} rectangles → "
                      f"Mode={config['mode']}, Sens={config['sensitivity']}, DPI={config['dpi']}")
            
            return data
            
        else:
            error_data = response.json()
            print(f"❌ Erreur: {error_data.get('error', 'Erreur inconnue')}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au serveur (localhost:5000)")
        return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

if __name__ == "__main__":
    print("🔧 OUTIL DE DEBUG AVANCÉ POUR PDF")
    print("=" * 60)
    
    import sys
    
    if len(sys.argv) > 1:
        # Mode ligne de commande
        if sys.argv[1] == "visual":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            mode = sys.argv[3] if len(sys.argv) > 3 else 'high_contrast'
            test_visual_debug(page, mode=mode)
        elif sys.argv[1] == "problem":
            test_problematic_pages()
        else:
            page = int(sys.argv[1])
            test_page(page)
    else:
        # Mode interactif
        print("Choisissez un test:")
        print("1️⃣ Test page unique avec logs détaillés")
        print("2️⃣ Test multi-pages rapide")
        print("3️⃣ Test sensibilités")
        print("4️⃣ 🚨 Recherche pages problématiques")
        print("5️⃣ 🎨 Debug visuel (images)")
        print("6️⃣ 🔍 Analyse rectangles manqués (pages 163/258)")
        
        choice = input("\nVotre choix (1-6): ").strip()
        
        if choice == "1":
            page = input("Numéro de page (défaut: 10): ").strip()
            page = int(page) if page.isdigit() else 10
            test_page(page)
            
        elif choice == "2":
            test_multiple_pages()
            
        elif choice == "3":
            test_sensitivity_comparison()
            
        elif choice == "4":
            test_problematic_pages()
            
        elif choice == "5":
            page = input("Page pour debug visuel (défaut: 10): ").strip()
            page = int(page) if page.isdigit() else 10
            mode = input("Mode (general/high_contrast/documents, défaut: high_contrast): ").strip()
            mode = mode if mode in ['general', 'high_contrast', 'documents'] else 'high_contrast'
            test_visual_debug(page, mode=mode)
            
        elif choice == "6":
            page = input("Page avec rectangles manqués (163 ou 258): ").strip()
            page = int(page) if page.isdigit() else 163
            test_missing_rectangles_debug(page)
            
        else:
            print("❌ Choix invalide")
    
    print("\n🎉 Debug terminé!")
    print("💡 Conseils:")
    print("   - Utilisez le debug visuel pour voir exactement ce qui se passe")
    print("   - Les logs détaillés vous donnent les statistiques précises")
    print("   - Testez différents modes si une page pose problème") 