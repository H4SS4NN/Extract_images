#!/usr/bin/env python3
"""
Correcteur manuel interactif pour les extractions Dubuffet
Permet de corriger manuellement les erreurs de numérotation
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from utils import logger

class DubuffetManualCorrector:
    """
    Correcteur manuel interactif pour les extractions Dubuffet
    """
    
    def __init__(self):
        self.logger = logger
        
    def interactive_correction_session(self, extraction_dir: str):
        """
        Session de correction interactive
        """
        extraction_path = Path(extraction_dir)
        if not extraction_path.exists():
            print(f"❌ Répertoire non trouvé: {extraction_dir}")
            return
        
        print(f"🎨 SESSION DE CORRECTION DUBUFFET")
        print(f"📁 Répertoire: {extraction_path.name}")
        print("=" * 60)
        
        corrections_made = []
        
        # Parcourir chaque page
        for page_dir in sorted(extraction_path.glob('page_*')):
            if page_dir.is_dir():
                page_corrections = self._correct_page_interactive(page_dir)
                corrections_made.extend(page_corrections)
        
        # Sauvegarder les corrections
        if corrections_made:
            self._save_corrections(extraction_path, corrections_made)
            print(f"\n✅ {len(corrections_made)} corrections appliquées et sauvegardées")
        else:
            print(f"\n📋 Aucune correction nécessaire")
    
    def _correct_page_interactive(self, page_dir: Path) -> List[Dict]:
        """
        Correction interactive d'une page
        """
        page_num = int(page_dir.name.split('_')[1])
        print(f"\n📄 PAGE {page_num}")
        print("-" * 30)
        
        # Lire le JSON de détails
        json_file = page_dir / 'page_ultra_details.json'
        if not json_file.exists():
            print(f"❌ JSON non trouvé pour la page {page_num}")
            return []
        
        with open(json_file, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
        
        rectangles = page_data.get('rectangles_details', [])
        if not rectangles:
            print(f"📭 Aucune image détectée sur la page {page_num}")
            return []
        
        corrections = []
        
        # Afficher les détections actuelles
        print(f"🔍 Images détectées sur la page {page_num}:")
        for i, rect in enumerate(rectangles, 1):
            filename = rect.get('filename', 'N/A')
            number = rect.get('artwork_number', 'N/A')
            method = rect.get('detection_method', 'N/A')
            confidence = rect.get('confidence', 0)
            
            print(f"   {i}. {filename} → Numéro: {number} (confiance: {confidence:.2f}, méthode: {method})")
        
        # Détecter les problèmes évidents
        detected_numbers = [rect.get('artwork_number') for rect in rectangles if rect.get('artwork_number')]
        number_counts = {}
        for num in detected_numbers:
            number_counts[num] = number_counts.get(num, 0) + 1
        
        # Signaler les duplicatas
        duplicates = [num for num, count in number_counts.items() if count > 1]
        if duplicates:
            print(f"⚠️  Duplicatas détectés: {duplicates}")
        
        # Demander s'il y a des corrections à faire
        while True:
            response = input(f"\n❓ Y a-t-il des erreurs à corriger sur la page {page_num} ? (o/n/details): ").strip().lower()
            
            if response in ['n', 'non', 'no']:
                break
            elif response in ['d', 'details']:
                self._show_page_details(page_dir, rectangles)
                continue
            elif response in ['o', 'oui', 'y', 'yes']:
                page_corrections = self._make_corrections_for_page(page_dir, rectangles)
                corrections.extend(page_corrections)
                break
            else:
                print("Réponse non reconnue. Tapez 'o' pour oui, 'n' pour non, ou 'details' pour plus d'infos.")
        
        return corrections
    
    def _show_page_details(self, page_dir: Path, rectangles: List[Dict]):
        """
        Affiche les détails d'une page
        """
        print(f"\n📋 DÉTAILS DE LA PAGE {page_dir.name}")
        print("-" * 40)
        
        # Vérifier si l'image complète existe
        full_image_path = page_dir / 'page_full_image.jpg'
        if full_image_path.exists():
            print(f"🖼️  Image complète: {full_image_path.name}")
        
        # Lister tous les fichiers d'images
        image_files = list(page_dir.glob('*.png'))
        print(f"📸 Images extraites: {len(image_files)}")
        for img_file in image_files:
            size_mb = img_file.stat().st_size / (1024 * 1024)
            print(f"   - {img_file.name} ({size_mb:.1f} MB)")
        
        # Afficher les bounding boxes
        print(f"\n📐 Bounding boxes:")
        for i, rect in enumerate(rectangles, 1):
            bbox = rect.get('bbox', {})
            x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)
            print(f"   {i}. {rect.get('filename')}: x={x}, y={y}, w={w}, h={h}")
    
    def _make_corrections_for_page(self, page_dir: Path, rectangles: List[Dict]) -> List[Dict]:
        """
        Effectue les corrections pour une page
        """
        corrections = []
        page_num = int(page_dir.name.split('_')[1])
        
        print(f"\n🔧 CORRECTION DE LA PAGE {page_num}")
        print("Tapez le numéro de l'image à corriger, ou 'fin' pour terminer")
        
        while True:
            # Afficher la liste des images
            print(f"\n📋 Images disponibles:")
            for i, rect in enumerate(rectangles, 1):
                filename = rect.get('filename', 'N/A')
                number = rect.get('artwork_number', 'N/A')
                print(f"   {i}. {filename} → {number}")
            
            choice = input(f"\n🎯 Quelle image corriger (1-{len(rectangles)}) ou 'fin' ? ").strip()
            
            if choice.lower() in ['fin', 'exit', 'quit']:
                break
            
            try:
                img_index = int(choice) - 1
                if 0 <= img_index < len(rectangles):
                    correction = self._correct_single_image(rectangles[img_index], page_num)
                    if correction:
                        corrections.append(correction)
                        # Mettre à jour le rectangle dans la liste
                        rectangles[img_index]['artwork_number'] = correction['new_number']
                        print(f"✅ Correction appliquée: {correction['old_number']} → {correction['new_number']}")
                else:
                    print(f"❌ Index invalide. Choisissez entre 1 et {len(rectangles)}")
            except ValueError:
                print("❌ Veuillez entrer un numéro valide ou 'fin'")
        
        return corrections
    
    def _correct_single_image(self, rectangle: Dict, page_num: int) -> Optional[Dict]:
        """
        Corrige une image individuelle
        """
        filename = rectangle.get('filename', 'N/A')
        old_number = rectangle.get('artwork_number', 'N/A')
        
        print(f"\n🎯 CORRECTION DE {filename}")
        print(f"   Numéro actuel: {old_number}")
        
        new_number = input(f"   Nouveau numéro (ou Entrée pour annuler): ").strip()
        
        if not new_number:
            print("   Correction annulée")
            return None
        
        if new_number == old_number:
            print("   Aucun changement")
            return None
        
        # Valider le nouveau numéro
        if not new_number.isdigit():
            print("   ❌ Le numéro doit être un nombre")
            return None
        
        reason = input(f"   Raison de la correction (optionnel): ").strip()
        if not reason:
            reason = f"Correction manuelle: {old_number} → {new_number}"
        
        return {
            'page': page_num,
            'filename': filename,
            'rectangle_id': rectangle.get('rectangle_id'),
            'old_number': old_number,
            'new_number': new_number,
            'reason': reason,
            'correction_type': 'manual'
        }
    
    def _save_corrections(self, extraction_path: Path, corrections: List[Dict]):
        """
        Sauvegarde les corrections appliquées
        """
        # Sauvegarder le fichier de corrections
        corrections_file = extraction_path / 'manual_corrections.json'
        corrections_data = {
            'correction_date': str(np.datetime64('now')),
            'total_corrections': len(corrections),
            'corrections': corrections
        }
        
        with open(corrections_file, 'w', encoding='utf-8') as f:
            json.dump(corrections_data, f, indent=2, ensure_ascii=False)
        
        print(f"📁 Corrections sauvegardées: {corrections_file}")
        
        # Appliquer les corrections aux fichiers JSON de chaque page
        for correction in corrections:
            page_num = correction['page']
            page_dir = extraction_path / f'page_{page_num:03d}'
            json_file = page_dir / 'page_ultra_details.json'
            
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                
                # Trouver et modifier le rectangle correspondant
                rectangles = page_data.get('rectangles_details', [])
                for rect in rectangles:
                    if (rect.get('rectangle_id') == correction['rectangle_id'] or 
                        rect.get('filename') == correction['filename']):
                        rect['artwork_number'] = correction['new_number']
                        rect['manually_corrected'] = True
                        rect['correction_reason'] = correction['reason']
                        break
                
                # Sauvegarder le JSON modifié
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(page_data, f, indent=2, ensure_ascii=False)
                
                print(f"📝 Page {page_num} mise à jour")
    
    def create_corrected_dubuffet_json(self, extraction_dir: str) -> Dict:
        """
        Crée le JSON final Dubuffet avec toutes les corrections appliquées
        """
        extraction_path = Path(extraction_dir)
        
        artworks = {}
        total_pages = 0
        total_corrections = 0
        
        # Parcourir toutes les pages
        for page_dir in extraction_path.glob('page_*'):
            if page_dir.is_dir():
                page_num = int(page_dir.name.split('_')[1])
                total_pages += 1
                
                json_file = page_dir / 'page_ultra_details.json'
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                    
                    for rect in page_data.get('rectangles_details', []):
                        number = rect.get('artwork_number')
                        if number:
                            # Compter les corrections
                            if rect.get('manually_corrected'):
                                total_corrections += 1
                            
                            artworks[number] = {
                                'number': number,
                                'title': f"HERBAGES AU CORBEAU {number}" if number in ['2', '3'] else f"ŒUVRE {number}",
                                'technique': 'huile sur toile',
                                'dimensions': 'dimensions à préciser',
                                'date': 'octobre 1952',
                                'page': page_num,
                                'filename': rect.get('filename'),
                                'thumbnail': rect.get('thumbnail'),
                                'bbox': rect.get('bbox'),
                                'confidence': rect.get('confidence'),
                                'detection_method': rect.get('detection_method'),
                                'collection': 'Dubuffet',
                                'manually_corrected': rect.get('manually_corrected', False),
                                'correction_reason': rect.get('correction_reason', '')
                            }
        
        return {
            'collection': 'Jean Dubuffet - Lieux momentanés',
            'extraction_date': str(np.datetime64('now')),
            'total_artworks': len(artworks),
            'total_pages_processed': total_pages,
            'manual_corrections_applied': total_corrections,
            'artworks': artworks,
            'notes': 'JSON généré après corrections manuelles interactives'
        }


def main():
    """Fonction principale"""
    print("✏️ CORRECTEUR MANUEL DUBUFFET")
    print("=" * 50)
    
    corrector = DubuffetManualCorrector()
    
    extraction_dir = input("📁 Chemin du répertoire d'extraction: ").strip()
    
    if not extraction_dir:
        extraction_dir = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-VIII_ULTRA_20250910_142409"
    
    if not os.path.exists(extraction_dir):
        print(f"❌ Répertoire non trouvé: {extraction_dir}")
        return
    
    # Session de correction interactive
    corrector.interactive_correction_session(extraction_dir)
    
    # Générer le JSON final corrigé
    print(f"\n📝 Génération du JSON final corrigé...")
    final_json = corrector.create_corrected_dubuffet_json(extraction_dir)
    
    # Sauvegarder
    output_file = Path(extraction_dir) / 'dubuffet_final_corrected.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON final sauvegardé: {output_file}")
    print(f"📊 {final_json['total_artworks']} œuvres, {final_json['manual_corrections_applied']} corrections appliquées")


if __name__ == "__main__":
    main()
