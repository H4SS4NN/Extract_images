"""
Analyseur de cohérence des numéros d'œuvres
"""
from typing import List, Dict, Any, Tuple
from utils import logger
from config import COHERENCE_CONFIG

class CoherenceAnalyzer:
    """Analyse la cohérence des numéros d'œuvres sur une page"""
    
    def __init__(self):
        self.logger = logger
    
    def analyze(self, rectangles_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse la cohérence des numéros détectés"""
        # Extraire les numéros détectés avec leurs positions
        detected_numbers = self._extract_detected_numbers(rectangles_details)
        
        if len(detected_numbers) < COHERENCE_CONFIG['min_numbers_for_analysis']:
            return {'error': 'Pas assez de numéros pour analyser la cohérence'}
        
        # Trier par position (gauche à droite, haut en bas)
        detected_numbers.sort(key=lambda x: (x['y'], x['x']))
        
        # Analyser la cohérence
        numbers = [item['number'] for item in detected_numbers]
        coherence_analysis = {
            'detected_numbers': numbers,
            'is_sequential': self._is_sequential(numbers),
            'gaps': self._find_gaps(numbers),
            'inconsistencies': [],
            'suggested_corrections': []
        }
        
        # Détecter les incohérences
        if not coherence_analysis['is_sequential']:
            coherence_analysis['inconsistencies'] = self._find_inconsistencies(detected_numbers)
        
        return coherence_analysis
    
    def _extract_detected_numbers(self, rectangles_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extrait les numéros détectés avec leurs positions"""
        detected_numbers = []
        
        for rect in rectangles_details:
            artwork_number = rect.get('artwork_number')
            if artwork_number and artwork_number.isdigit():
                bbox = rect.get('bbox', {})
                detected_numbers.append({
                    'number': int(artwork_number),
                    'x': bbox.get('x', 0),
                    'y': bbox.get('y', 0),
                    'w': bbox.get('w', 0),
                    'h': bbox.get('h', 0),
                    'filename': rect.get('filename', ''),
                    'confidence': rect.get('confidence', 0)
                })
        
        return detected_numbers
    
    def _is_sequential(self, numbers: List[int]) -> bool:
        """Vérifie si les numéros sont séquentiels"""
        if len(numbers) < 2:
            return True
        
        sorted_numbers = sorted(numbers)
        for i in range(1, len(sorted_numbers)):
            if sorted_numbers[i] - sorted_numbers[i-1] != 1:
                return False
        return True
    
    def _find_gaps(self, numbers: List[int]) -> List[int]:
        """Trouve les gaps dans la séquence de numéros"""
        if len(numbers) < 2:
            return []
        
        sorted_numbers = sorted(numbers)
        gaps = []
        
        for i in range(1, len(sorted_numbers)):
            diff = sorted_numbers[i] - sorted_numbers[i-1]
            if diff > 1:
                # Il y a un gap
                for missing in range(sorted_numbers[i-1] + 1, sorted_numbers[i]):
                    gaps.append(missing)
        
        return gaps
    
    def _find_inconsistencies(self, detected_numbers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trouve les incohérences dans les numéros détectés"""
        inconsistencies = []
        
        # Vérifier les numéros dupliqués
        numbers = [item['number'] for item in detected_numbers]
        duplicates = [num for num in set(numbers) if numbers.count(num) > 1]
        
        for dup in duplicates:
            inconsistencies.append({
                'type': 'duplicate',
                'number': dup,
                'count': numbers.count(dup)
            })
        
        # Vérifier les numéros très éloignés
        if len(numbers) > 1:
            sorted_numbers = sorted(numbers)
            for i in range(1, len(sorted_numbers)):
                diff = sorted_numbers[i] - sorted_numbers[i-1]
                if diff > COHERENCE_CONFIG['max_gap_threshold']:
                    inconsistencies.append({
                        'type': 'large_gap',
                        'gap_start': sorted_numbers[i-1],
                        'gap_end': sorted_numbers[i],
                        'gap_size': diff
                    })
        
        return inconsistencies
