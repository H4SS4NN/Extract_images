#!/usr/bin/env python3
"""
Script de test pour vérifier que le système de validation fonctionne
"""

import os
import json
import requests
import time
from datetime import datetime

def test_server_connection():
    """Tester la connexion au serveur"""
    try:
        response = requests.get('http://localhost:5000/api/stats', timeout=5)
        if response.status_code == 200:
            print("✅ Serveur accessible")
            data = response.json()
            print(f"   📊 {data['total_sessions']} sessions, {data['total_images']} images")
            return True
        else:
            print(f"❌ Serveur répond mais erreur {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Serveur non accessible sur http://localhost:5000")
        return False
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return False

def test_sessions():
    """Tester la récupération des sessions"""
    try:
        response = requests.get('http://localhost:5000/api/sessions')
        if response.status_code == 200:
            data = response.json()
            sessions = data['sessions']
            print(f"✅ {len(sessions)} sessions trouvées")
            
            if sessions:
                for i, session in enumerate(sessions[:3], 1):
                    print(f"   {i}. {session['name']} ({session['total_pages']} pages)")
            
            return len(sessions) > 0
        else:
            print(f"❌ Erreur récupération sessions: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test sessions: {e}")
        return False

def test_page_images():
    """Tester la récupération d'images de page"""
    try:
        # D'abord récupérer les données de session
        response = requests.get('http://localhost:5000/api/get-session-data')
        if response.status_code != 200:
            print("❌ Pas de session active")
            return False
        
        session_data = response.json()
        print(f"✅ Session active: {session_data['sessionName']}")
        
        # Tester la première page
        response = requests.get('http://localhost:5000/api/get-page-images/1')
        if response.status_code == 200:
            data = response.json()
            images = data['images']
            print(f"✅ Page 1: {len(images)} images")
            
            if images:
                doubtful = len([img for img in images if img['is_doubtful']])
                print(f"   📷 {len(images) - doubtful} normales, {doubtful} douteuses")
            
            return True
        else:
            print(f"❌ Erreur récupération images page 1: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test images: {e}")
        return False

def test_save_validation():
    """Tester la sauvegarde de validation"""
    try:
        test_data = {
            'sessionName': 'TEST_SESSION',
            'totalPages': 1,
            'imageStates': {
                'page1_test1.png': 'validated',
                'page1_test2.png': 'rejected',
                'page1_test3.png': 'doubtful'
            },
            'summary': {
                'validated': 1,
                'rejected': 1,
                'doubtful': 1,
                'pending': 0
            }
        }
        
        response = requests.post('http://localhost:5000/api/save-validation', 
                               json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Sauvegarde validation OK")
            print(f"   📁 Fichier: {result.get('file', 'N/A')}")
            return True
        else:
            print(f"❌ Erreur sauvegarde validation: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test sauvegarde: {e}")
        return False

def check_extraction_folders():
    """Vérifier la structure des dossiers d'extraction"""
    extractions_dir = "extractions_ultra"
    
    if not os.path.exists(extractions_dir):
        print(f"❌ Dossier {extractions_dir} non trouvé")
        print("   💡 Lancez d'abord extract_pdf_ultra_sensible.py")
        return False
    
    sessions = [d for d in os.listdir(extractions_dir) 
                if os.path.isdir(os.path.join(extractions_dir, d))]
    
    print(f"✅ Dossier extractions trouvé: {len(sessions)} sessions")
    
    if sessions:
        # Analyser la première session
        first_session = sessions[0]
        session_path = os.path.join(extractions_dir, first_session)
        
        # Vérifier les fichiers de métadonnées
        meta_file = os.path.join(session_path, "extraction_ultra_complete.json")
        if os.path.exists(meta_file):
            print("✅ Métadonnées session trouvées")
            
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            print(f"   📄 PDF: {meta.get('pdf_name', 'N/A')}")
            print(f"   📊 {meta.get('total_pages', 0)} pages, {meta.get('total_images_extracted', 0)} images")
        else:
            print("⚠️ Métadonnées session manquantes")
        
        # Vérifier les dossiers de pages
        page_dirs = [d for d in os.listdir(session_path) 
                     if d.startswith('page_') and os.path.isdir(os.path.join(session_path, d))]
        
        print(f"✅ {len(page_dirs)} dossiers de pages trouvés")
        
        if page_dirs:
            # Analyser la première page
            first_page = page_dirs[0]
            page_path = os.path.join(session_path, first_page)
            
            images = [f for f in os.listdir(page_path) 
                     if f.endswith('.png') and not f.startswith('thumb_')]
            
            doubtful_dir = os.path.join(page_path, "DOUTEUX")
            doubtful_images = []
            if os.path.exists(doubtful_dir):
                doubtful_images = [f for f in os.listdir(doubtful_dir) 
                                  if f.endswith('.png') and not f.startswith('thumb_')]
            
            print(f"   📷 {first_page}: {len(images)} images normales, {len(doubtful_images)} douteuses")
    
    return True

def main():
    """Test principal"""
    print("🧪 TEST DU SYSTÈME DE VALIDATION PDF ULTRA")
    print("=" * 60)
    
    print("\n1. 📁 Vérification des dossiers d'extraction...")
    folders_ok = check_extraction_folders()
    
    print("\n2. 🌐 Test de connexion au serveur...")
    server_ok = test_server_connection()
    
    if not server_ok:
        print("\n💡 Pour démarrer le serveur:")
        print("   - Windows: double-clic sur start_validation_server.bat")
        print("   - Manuel: python server_validation.py")
        return
    
    print("\n3. 📋 Test des sessions...")
    sessions_ok = test_sessions()
    
    if sessions_ok:
        print("\n4. 🖼️ Test des images de page...")
        images_ok = test_page_images()
        
        print("\n5. 💾 Test de sauvegarde...")
        save_ok = test_save_validation()
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS:")
    print(f"   📁 Dossiers extraction: {'✅' if folders_ok else '❌'}")
    print(f"   🌐 Serveur: {'✅' if server_ok else '❌'}")
    
    if server_ok:
        print(f"   📋 Sessions: {'✅' if sessions_ok else '❌'}")
        if sessions_ok:
            print(f"   🖼️ Images: {'✅' if images_ok else '❌'}")
            print(f"   💾 Sauvegarde: {'✅' if save_ok else '❌'}")
    
    print("\n🎯 PROCHAINES ÉTAPES:")
    if folders_ok and server_ok and sessions_ok:
        print("   1. Ouvrir http://localhost:5000 dans votre navigateur")
        print("   2. Commencer la validation des images")
        print("   3. Exporter les résultats quand terminé")
    else:
        if not folders_ok:
            print("   1. Lancer extract_pdf_ultra_sensible.py pour créer des extractions")
        if not server_ok:
            print("   2. Démarrer server_validation.py")
        print("   3. Relancer ce test")

if __name__ == "__main__":
    main()
