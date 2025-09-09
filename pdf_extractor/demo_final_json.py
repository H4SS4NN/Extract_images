#!/usr/bin/env python3
"""
Démonstration du générateur de JSON final
"""

import os
import sys
import json
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from analyzers.final_json_generator import FinalJSONGenerator

def demo_final_json():
    """Démonstration du générateur de JSON final"""
    print("🎯 DÉMONSTRATION GÉNÉRATEUR JSON FINAL")
    print("=" * 50)
    
    # Créer le générateur
    generator = FinalJSONGenerator()
    
    # Données d'exemple (simulant une session d'extraction)
    session_data = {
        "pdf_name": "PABLO-PICASSO-VOL20-1961-1962.pdf",
        "start_time": "2025-09-08T16:08:40",
        "pages": [
            {
                "page_number": 1,
                "page_dir": "extractions_ultra/test_session/page_001",
                "rectangles_details": [
                    {
                        "artwork_number": 1,
                        "filename": "1.png",
                        "is_doubtful": False,
                        "confidence": 0.9,
                        "detection_method": "ultra_detector",
                        "bbox": {"x": 100, "y": 200, "w": 300, "h": 400},
                        "area": 120000
                    },
                    {
                        "artwork_number": 2,
                        "filename": "2.png",
                        "is_doubtful": True,
                        "confidence": 0.6,
                        "detection_method": "template_detector",
                        "bbox": {"x": 500, "y": 300, "w": 250, "h": 350},
                        "area": 87500,
                        "doubt_reasons": ["taille_anormale", "peu_de_contenu"]
                    }
                ],
                "summary_analysis": {
                    "is_summary": True,
                    "entries": [
                        {
                            "artwork_number": 1,
                            "artist_name": "Pablo Picasso",
                            "title": "Les Demoiselles d'Avignon",
                            "medium": "huile sur toile",
                            "size": [243.9, 233.7],
                            "size_unit": "cm",
                            "execution_year": 1907,
                            "signature": True,
                            "description": "Pablo Picasso, Les Demoiselles d'Avignon, 1907, huile sur toile, 243.9 x 233.7 cm, signé",
                            "provenance": ["Collection privée"],
                            "literature": ["Picasso, Catalogue Raisonné, 1996"],
                            "exhibition": ["Musée Picasso, Paris, 2019"],
                            "extraction_method": "mistral"
                        },
                        {
                            "artwork_number": 2,
                            "artist_name": "Pablo Picasso",
                            "title": "Guernica",
                            "medium": "huile sur toile",
                            "size": [349.3, 776.6],
                            "size_unit": "cm",
                            "execution_year": 1937,
                            "signature": True,
                            "description": "Pablo Picasso, Guernica, 1937, huile sur toile, 349.3 x 776.6 cm, signé",
                            "provenance": ["Museo Reina Sofía, Madrid"],
                            "literature": ["Picasso, Guernica, 1937"],
                            "exhibition": ["Museo Reina Sofía, Madrid, 2020"],
                            "extraction_method": "mistral"
                        }
                    ]
                }
            }
        ]
    }
    
    # Créer un dossier de test
    test_dir = "test_final_json"
    os.makedirs(test_dir, exist_ok=True)
    
    # Créer des images factices
    page_dir = os.path.join(test_dir, "extractions_ultra", "test_session", "page_001")
    os.makedirs(page_dir, exist_ok=True)
    
    # Créer des fichiers d'images factices
    for i in [1, 2]:
        image_path = os.path.join(page_dir, f"{i}.png")
        with open(image_path, 'w') as f:
            f.write("fake image data")
    
    # Mettre à jour le chemin dans les données
    session_data["pages"][0]["page_dir"] = page_dir
    
    print("📊 Données d'exemple:")
    print(f"  - PDF: {session_data['pdf_name']}")
    print(f"  - Pages: {len(session_data['pages'])}")
    print(f"  - Images: {len(session_data['pages'][0]['rectangles_details'])}")
    print(f"  - Entrées sommaire: {len(session_data['pages'][0]['summary_analysis']['entries'])}")
    
    print("\n🎯 Génération du JSON final...")
    
    # Générer le JSON final
    final_data = generator.generate_final_json(session_data, test_dir)
    
    print(f"✅ JSON final généré!")
    print(f"  - Œuvres traitées: {len(final_data['artworks'])}")
    
    # Afficher un exemple d'œuvre
    if final_data['artworks']:
        print("\n📝 Exemple d'œuvre générée:")
        artwork = final_data['artworks'][0]
        print(f"  - ID: {artwork['id']}")
        print(f"  - Artiste: {artwork['artist_name']}")
        print(f"  - Titre: {artwork['title']}")
        print(f"  - Image: {artwork['image_filename']}")
        print(f"  - Dimensions: {artwork['size']} {artwork['size_unit']}")
        print(f"  - Année: {artwork['execution_year']}")
        print(f"  - Signature: {artwork['signature']}")
        print(f"  - Douteuse: {artwork['metadata']['is_doubtful']}")
    
    # Créer des JSON individuels
    print("\n📁 Création des JSON individuels...")
    generator.create_individual_jsons(final_data, test_dir)
    
    # Créer le rapport
    print("📄 Création du rapport de synthèse...")
    generator.create_summary_report(final_data, test_dir)
    
    print("\n✅ Démonstration terminée!")
    print(f"📁 Fichiers créés dans: {test_dir}")
    print("  - final_artworks.json: JSON complet")
    print("  - individual_artworks/: JSON individuels")
    print("  - extraction_report.md: Rapport de synthèse")
    
    # Afficher un extrait du JSON final
    print("\n📋 Extrait du JSON final:")
    print(json.dumps(final_data['artworks'][0], indent=2, ensure_ascii=False)[:500] + "...")

if __name__ == "__main__":
    demo_final_json()

