#!/usr/bin/env python3
"""
Analyseur et correcteur pour les extractions Dubuffet
Analyse les erreurs de détection et propose des corrections
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

class DubuffetAnalyzer:
    """
    Analyseur spécialisé pour les extractions Dubuffet
    """
    
    def __init__(self):
        self.logger = logger
        
    def analyze_extraction_directory(self, extraction_dir: str) -> Dict:
        """
        Analyse un répertoire d'extraction complet
        """
        extraction_path = Path(extraction_dir)
        if not extraction_path.exists():
            self.logger.error(f"❌ Répertoire non trouvé: {extraction_dir}")
            return {}
            
        analysis_results = {
            'extraction_dir': str(extraction_path),
            'total_pages': 0,
            'total_images': 0,
            'errors_detected': [],
            'corrections_suggested': [],
            'pages_analysis': {}
        }
        
        # Analyser chaque page
        for page_dir in extraction_path.glob('page_*'):
            if page_dir.is_dir():
                page_num = int(page_dir.name.split('_')[1])
                page_analysis = self.analyze_page(page_dir)
                analysis_results['pages_analysis'][page_num] = page_analysis
                analysis_results['total_pages'] += 1
                analysis_results['total_images'] += page_analysis.get('images_count', 0)
                
                # Collecter les erreurs
                if page_analysis.get('errors'):
                    analysis_results['errors_detected'].extend(page_analysis['errors'])
                
                # Collecter les corrections
                if page_analysis.get('corrections'):
                    analysis_results['corrections_suggested'].extend(page_analysis['corrections'])
        
        return analysis_results
    
    def analyze_page(self, page_dir: Path) -> Dict:
        """
        Analyse une page spécifique
        """
        self.logger.info(f"🔍 Analyse de {page_dir.name}")
        
        # Lire le JSON de détails
        json_file = page_dir / 'page_ultra_details.json'
        if not json_file.exists():
            return {'error': 'JSON de détails non trouvé'}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
        
        analysis = {
            'page_number': page_data.get('page_number'),
            'images_count': len(page_data.get('rectangles_details', [])),
            'detected_numbers': [],
            'errors': [],
            'corrections': [],
            'image_files': []
        }
        
        # Analyser les numéros détectés
        rectangles = page_data.get('rectangles_details', [])
        number_counts = {}
        
        for rect in rectangles:
            number = rect.get('artwork_number')
            if number:
                try:
                    num_int = int(number)
                    analysis['detected_numbers'].append(num_int)
                    number_counts[num_int] = number_counts.get(num_int, 0) + 1
                    analysis['image_files'].append(rect.get('filename'))
                except ValueError:
                    analysis['errors'].append({
                        'type': 'invalid_number',
                        'number': number,
                        'message': f"Numéro non valide: {number}"
                    })
        
        # Détecter les duplicatas
        for number, count in number_counts.items():
            if count > 1:
                analysis['errors'].append({
                    'type': 'duplicate_number',
                    'number': number,
                    'count': count,
                    'message': f"Numéro {number} détecté {count} fois"
                })
        
        # Analyser la séquence de numéros
        if analysis['detected_numbers']:
            sorted_numbers = sorted(set(analysis['detected_numbers']))
            gaps = self._find_gaps(sorted_numbers)
            if gaps:
                analysis['errors'].append({
                    'type': 'sequence_gaps',
                    'gaps': gaps,
                    'message': f"Numéros manquants: {gaps}"
                })
        
        # Proposer des corrections
        corrections = self._suggest_corrections(analysis, rectangles)
        analysis['corrections'] = corrections
        
        return analysis
    
    def _find_gaps(self, numbers: List[int]) -> List[int]:
        """Trouve les gaps dans une séquence de numéros"""
        if len(numbers) < 2:
            return []
        
        gaps = []
        for i in range(numbers[0], numbers[-1]):
            if i not in numbers:
                gaps.append(i)
        return gaps
    
    def _suggest_corrections(self, analysis: Dict, rectangles: List[Dict]) -> List[Dict]:
        """
        Propose des corrections basées sur l'analyse
        """
        corrections = []
        
        # Correction pour les duplicatas
        for error in analysis.get('errors', []):
            if error['type'] == 'duplicate_number':
                number = error['number']
                count = error['count']
                
                # Trouver tous les rectangles avec ce numéro
                same_number_rects = [r for r in rectangles if r.get('artwork_number') == str(number)]
                
                if len(same_number_rects) > 1:
                    # Proposer une re-numérotation séquentielle
                    base_number = number
                    for i, rect in enumerate(same_number_rects):
                        if i > 0:  # Garder le premier, changer les autres
                            new_number = base_number + i
                            corrections.append({
                                'type': 'renumber',
                                'original_number': number,
                                'new_number': new_number,
                                'rectangle_id': rect.get('rectangle_id'),
                                'filename': rect.get('filename'),
                                'reason': f"Correction duplicata: {number} → {new_number}"
                            })
        
        return corrections
    
    def generate_corrected_json(self, page_dir: Path, corrections: List[Dict]) -> Dict:
        """
        Génère un JSON corrigé avec les corrections appliquées
        """
        json_file = page_dir / 'page_ultra_details.json'
        with open(json_file, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
        
        corrected_data = original_data.copy()
        
        # Appliquer les corrections
        rectangles = corrected_data.get('rectangles_details', [])
        for correction in corrections:
            if correction['type'] == 'renumber':
                rect_id = correction['rectangle_id']
                new_number = correction['new_number']
                
                # Trouver et modifier le rectangle
                for rect in rectangles:
                    if rect.get('rectangle_id') == rect_id:
                        rect['artwork_number'] = str(new_number)
                        rect['corrected'] = True
                        rect['correction_reason'] = correction['reason']
                        break
        
        # Recalculer l'analyse de cohérence
        numbers = []
        for rect in rectangles:
            try:
                numbers.append(int(rect.get('artwork_number', 0)))
            except ValueError:
                pass
        
        corrected_data['coherence_analysis'] = {
            'detected_numbers': numbers,
            'is_sequential': len(numbers) == len(set(numbers)) and numbers == list(range(min(numbers), max(numbers) + 1)),
            'gaps': self._find_gaps(sorted(set(numbers))),
            'corrections_applied': len(corrections)
        }
        
        return corrected_data
    
    def create_dubuffet_artwork_json(self, extraction_dir: str) -> Dict:
        """
        Crée un JSON d'œuvres au format Dubuffet (similaire à Picasso)
        """
        analysis = self.analyze_extraction_directory(extraction_dir)
        
        artworks = {}
        for page_num, page_analysis in analysis.get('pages_analysis', {}).items():
            page_dir = Path(extraction_dir) / f'page_{page_num:03d}'
            
            if page_dir.exists():
                json_file = page_dir / 'page_ultra_details.json'
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                    
                    for rect in page_data.get('rectangles_details', []):
                        number = rect.get('artwork_number')
                        if number:
                            artworks[number] = {
                                'number': number,
                                'title': f"ŒUVRE {number}",  # Titre générique pour Dubuffet
                                'technique': 'huile sur toile',  # Technique par défaut
                                'dimensions': 'dimensions à préciser',
                                'date': 'date à préciser',
                                'page': page_num,
                                'filename': rect.get('filename'),
                                'thumbnail': rect.get('thumbnail'),
                                'bbox': rect.get('bbox'),
                                'confidence': rect.get('confidence'),
                                'detection_method': rect.get('detection_method'),
                                'collection': 'Dubuffet'
                            }
        
        return {
            'collection': 'Jean Dubuffet',
            'extraction_date': analysis.get('extraction_date'),
            'total_artworks': len(artworks),
            'artworks': artworks,
            'analysis_summary': {
                'total_pages': analysis.get('total_pages'),
                'total_images': analysis.get('total_images'),
                'errors_count': len(analysis.get('errors_detected', [])),
                'corrections_count': len(analysis.get('corrections_suggested', []))
            }
        }


def main():
    """Fonction principale pour tester l'analyseur"""
    print("🎨 ANALYSEUR DUBUFFET")
    print("=" * 50)
    
    analyzer = DubuffetAnalyzer()
    
    # Analyser le répertoire d'extraction fourni
    extraction_dir = input("📁 Chemin du répertoire d'extraction (ou Entrée pour exemple): ").strip()
    
    if not extraction_dir:
        # Utiliser l'exemple fourni
        extraction_dir = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-VIII_ULTRA_20250910_142409"
    
    if not os.path.exists(extraction_dir):
        print(f"❌ Répertoire non trouvé: {extraction_dir}")
        return
    
    print(f"\n🔍 Analyse de: {extraction_dir}")
    
    # Analyse complète
    analysis = analyzer.analyze_extraction_directory(extraction_dir)
    
    print(f"\n📊 RÉSULTATS D'ANALYSE:")
    print(f"   - Pages analysées: {analysis['total_pages']}")
    print(f"   - Images totales: {analysis['total_images']}")
    print(f"   - Erreurs détectées: {len(analysis['errors_detected'])}")
    print(f"   - Corrections suggérées: {len(analysis['corrections_suggested'])}")
    
    # Afficher les erreurs
    if analysis['errors_detected']:
        print(f"\n❌ ERREURS DÉTECTÉES:")
        for i, error in enumerate(analysis['errors_detected'], 1):
            print(f"   {i}. {error['message']}")
    
    # Afficher les corrections
    if analysis['corrections_suggested']:
        print(f"\n🔧 CORRECTIONS SUGGÉRÉES:")
        for i, correction in enumerate(analysis['corrections_suggested'], 1):
            print(f"   {i}. {correction['reason']}")
    
    # Générer le JSON d'œuvres
    print(f"\n📝 Génération du JSON d'œuvres...")
    artworks_json = analyzer.create_dubuffet_artwork_json(extraction_dir)
    
    # Sauvegarder
    output_file = Path(extraction_dir) / 'dubuffet_artworks_corrected.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(artworks_json, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON d'œuvres sauvegardé: {output_file}")
    print(f"📊 {artworks_json['total_artworks']} œuvres répertoriées")


if __name__ == "__main__":
    main()
