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
    print("🚀 EXTRACTEUR PDF ULTRA SENSIBLE - MULTI-COLLECTIONS")
    print("=" * 70)
    print("🎯 MODE ULTRA : CAPTURE VRAIMENT TOUT !")
    print("✨ Multi-détection, seuils ultra-bas, DPI élevé")
    print("🔬 8+ algorithmes par page, fusion intelligente")
    print("☁️ Spécialisé pour fonds clairs et balance des blancs")
    print("🎨 Détection par saturation et contours doux")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Intégration Ollama pour correction automatique")
    print("🎭 Support multi-artistes : Picasso, Dubuffet, etc.")
    print("=" * 70)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Créer l'extracteur pour avoir accès aux collections
    temp_extractor = PDFExtractor()
    available_collections = temp_extractor.get_available_collections()
    
    # Tentative de détection automatique
    print(f"\n🔍 Collections disponibles: {', '.join(available_collections)}")
    detected_collection = temp_extractor.auto_detect_collection(pdf_path, "")
    
    if detected_collection:
        print(f"✨ Collection détectée automatiquement: {detected_collection}")
        use_detected = input(f"Utiliser '{detected_collection}' ? (O/n): ").strip().lower()
        if use_detected in ['', 'o', 'oui', 'y', 'yes']:
            selected_collection = detected_collection
        else:
            selected_collection = None
    else:
        selected_collection = None
    
    # Si pas de détection ou refusée, demander manuellement
    if not selected_collection:
        print(f"\n🎭 Choisir une collection:")
        for i, collection in enumerate(available_collections, 1):
            print(f"  {i}. {collection.title()}")
        
        collection_input = input(f"Collection (1-{len(available_collections)}, Entrée=Picasso): ").strip()
        
        if collection_input.isdigit() and 1 <= int(collection_input) <= len(available_collections):
            selected_collection = available_collections[int(collection_input) - 1]
        else:
            selected_collection = 'picasso'  # Par défaut
    
    print(f"✅ Collection sélectionnée: {selected_collection.title()}")
    
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
    
    # Créer l'extracteur ULTRA avec la collection sélectionnée
    extractor = PDFExtractor(collection_name=selected_collection)
    
    # Afficher les infos de la collection
    collection_info = extractor.collection.get_collection_info()
    print(f"\n🎨 Collection: {collection_info['name']}")
    print(f"📝 Description: {collection_info['description']}")
    print(f"📋 Sommaires: {'✅' if collection_info['has_summary'] else '❌'}")
    print(f"🎯 Zones de détection: {collection_info['detection_zones_count']}")
    
    # Lancer l'extraction ULTRA
    print("\n🚀 Extraction ULTRA en cours...")
    print("⚡ Chaque page testée avec 8+ méthodes différentes")
    print("🔬 Seuils ultra-permissifs, DPI élevé")
    print("☁️ Optimisé pour fonds clairs et balance des blancs")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Correction automatique avec Ollama si disponible")
    print(f"🎭 Optimisé pour: {selected_collection.title()}")
    
    success = extractor.extract_pdf(pdf_path, max_pages, start_page)
    
    if success:
        print("\n✅ Extraction ULTRA terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Mode ULTRA: Toutes les images devraient être capturées !")
    else:
        print("\n❌ Extraction ULTRA échouée!")

if __name__ == "__main__":
    main()
