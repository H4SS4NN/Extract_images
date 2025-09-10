#!/usr/bin/env python3
"""
Correcteur visuel pour les extractions Dubuffet
Analyse les images pour détecter et corriger les erreurs de numérotation
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
import pytesseract

class DubuffetVisualCorrector:
    """
    Correcteur visuel pour analyser les images et corriger les erreurs de numérotation
    """
    
    def __init__(self):
        self.logger = logger
        
    def analyze_page_images(self, page_dir: Path) -> Dict:
        """
        Analyse visuelle des images d'une page
        """
        self.logger.info(f"🔍 Analyse visuelle de {page_dir.name}")
        
        # Charger l'image complète de la page
        full_image_path = page_dir / 'page_full_image.jpg'
        if not full_image_path.exists():
            return {'error': 'Image complète non trouvée'}
        
        full_image = cv2.imread(str(full_image_path))
        if full_image is None:
            return {'error': 'Impossible de charger l\'image'}
        
        # Lire le JSON de détails
        json_file = page_dir / 'page_ultra_details.json'
        if not json_file.exists():
            return {'error': 'JSON de détails non trouvé'}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
        
        analysis = {
            'page_number': page_data.get('page_number'),
            'image_size': full_image.shape[:2],
            'rectangles_analysis': [],
            'visual_errors': [],
            'suggested_corrections': []
        }
        
        # Analyser chaque rectangle
        rectangles = page_data.get('rectangles_details', [])
        for rect in rectangles:
            rect_analysis = self._analyze_rectangle(full_image, rect)
            analysis['rectangles_analysis'].append(rect_analysis)
            
            # Détecter les erreurs visuelles
            errors = self._detect_visual_errors(rect_analysis)
            analysis['visual_errors'].extend(errors)
        
        # Proposer des corrections basées sur l'analyse visuelle
        corrections = self._suggest_visual_corrections(analysis, rectangles)
        analysis['suggested_corrections'] = corrections
        
        return analysis
    
    def _analyze_rectangle(self, full_image: np.ndarray, rect: Dict) -> Dict:
        """
        Analyse un rectangle spécifique
        """
        bbox = rect.get('bbox', {})
        x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)
        
        # Extraire la région d'intérêt
        roi = full_image[y:y+h, x:x+w]
        
        analysis = {
            'rectangle_id': rect.get('rectangle_id'),
            'filename': rect.get('filename'),
            'detected_number': rect.get('artwork_number'),
            'bbox': bbox,
            'roi_size': roi.shape[:2] if roi.size > 0 else (0, 0),
            'visual_features': {}
        }
        
        if roi.size > 0:
            # Analyser les caractéristiques visuelles
            analysis['visual_features'] = self._extract_visual_features(roi)
            
            # Rechercher le numéro dans les zones typiques de Dubuffet
            number_zones = self._find_dubuffet_number_zones(roi)
            analysis['number_zones'] = number_zones
            
            # Re-analyser le numéro avec OCR amélioré
            reanalyzed_number = self._reanalyze_number_ocr(roi)
            analysis['reanalyzed_number'] = reanalyzed_number
        
        return analysis
    
    def _extract_visual_features(self, roi: np.ndarray) -> Dict:
        """
        Extrait les caractéristiques visuelles d'une région
        """
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        features = {
            'mean_intensity': float(np.mean(gray)),
            'std_intensity': float(np.std(gray)),
            'has_text_regions': False,
            'text_confidence': 0.0
        }
        
        # Détecter les régions de texte
        try:
            # Préprocessing pour améliorer la détection de texte
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Détecter les contours pour trouver les régions de texte
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                area = w * h
                
                # Filtrer les régions qui pourraient contenir du texte
                if 0.2 < aspect_ratio < 10 and 50 < area < 5000:
                    text_regions.append((x, y, w, h))
            
            features['text_regions_count'] = len(text_regions)
            features['has_text_regions'] = len(text_regions) > 0
            
        except Exception as e:
            self.logger.debug(f"Erreur analyse visuelle: {e}")
        
        return features
    
    def _find_dubuffet_number_zones(self, roi: np.ndarray) -> List[Dict]:
        """
        Trouve les zones typiques où se trouvent les numéros dans les œuvres Dubuffet
        """
        h, w = roi.shape[:2]
        
        # Zones typiques pour Dubuffet (basées sur votre exemple)
        zones = [
            # Zone en bas à gauche (typique Dubuffet)
            {'name': 'bottom_left', 'x': 0, 'y': int(h*0.8), 'w': int(w*0.3), 'h': int(h*0.2)},
            # Zone en bas à droite
            {'name': 'bottom_right', 'x': int(w*0.7), 'y': int(h*0.8), 'w': int(w*0.3), 'h': int(h*0.2)},
            # Zone en bas centre
            {'name': 'bottom_center', 'x': int(w*0.3), 'y': int(h*0.85), 'w': int(w*0.4), 'h': int(h*0.15)},
            # Zone sous l'image (si l'image ne prend pas toute la hauteur)
            {'name': 'below_image', 'x': 0, 'y': int(h*0.9), 'w': w, 'h': int(h*0.1)},
        ]
        
        analyzed_zones = []
        for zone in zones:
            x, y, w_zone, h_zone = zone['x'], zone['y'], zone['w'], zone['h']
            
            # Vérifier les limites
            if x + w_zone <= w and y + h_zone <= h and w_zone > 0 and h_zone > 0:
                zone_roi = roi[y:y+h_zone, x:x+w_zone]
                
                if zone_roi.size > 0:
                    # Analyser cette zone avec OCR
                    number = self._ocr_zone(zone_roi)
                    analyzed_zones.append({
                        'name': zone['name'],
                        'bbox': zone,
                        'detected_number': number,
                        'confidence': self._calculate_number_confidence(number)
                    })
        
        return analyzed_zones
    
    def _ocr_zone(self, zone_roi: np.ndarray) -> Optional[str]:
        """
        Applique l'OCR sur une zone spécifique
        """
        try:
            # Préprocessing spécialisé pour les numéros
            gray = cv2.cvtColor(zone_roi, cv2.COLOR_BGR2GRAY)
            
            # Améliorer le contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Binarisation
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Agrandir pour l'OCR
            scale_factor = 3
            big = cv2.resize(binary, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            
            # OCR avec configuration pour numéros
            config = '--psm 8 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(big, config=config).strip()
            
            # Nettoyer et valider
            if text and text.isdigit() and 1 <= len(text) <= 3:
                return text
            
        except Exception as e:
            self.logger.debug(f"Erreur OCR zone: {e}")
        
        return None
    
    def _calculate_number_confidence(self, number: Optional[str]) -> float:
        """
        Calcule la confiance pour un numéro détecté
        """
        if not number:
            return 0.0
        
        if not number.isdigit():
            return 0.0
        
        # Plus le numéro est court et raisonnable, plus la confiance est élevée
        if len(number) == 1:
            return 0.9
        elif len(number) == 2:
            return 0.8
        elif len(number) == 3:
            return 0.7
        else:
            return 0.3
    
    def _reanalyze_number_ocr(self, roi: np.ndarray) -> Dict:
        """
        Re-analyse le numéro avec des techniques OCR améliorées
        """
        results = {
            'best_number': None,
            'confidence': 0.0,
            'all_candidates': []
        }
        
        # Tester différentes zones et préprocessings
        zones = self._find_dubuffet_number_zones(roi)
        
        for zone in zones:
            if zone['detected_number'] and zone['confidence'] > results['confidence']:
                results['best_number'] = zone['detected_number']
                results['confidence'] = zone['confidence']
            
            if zone['detected_number']:
                results['all_candidates'].append({
                    'number': zone['detected_number'],
                    'confidence': zone['confidence'],
                    'zone': zone['name']
                })
        
        return results
    
    def _detect_visual_errors(self, rect_analysis: Dict) -> List[Dict]:
        """
        Détecte les erreurs visuelles dans l'analyse d'un rectangle
        """
        errors = []
        
        detected_number = rect_analysis.get('detected_number')
        reanalyzed = rect_analysis.get('reanalyzed_number', {})
        best_reanalyzed = reanalyzed.get('best_number')
        
        # Vérifier si la re-analyse donne un résultat différent et plus fiable
        if (best_reanalyzed and 
            best_reanalyzed != detected_number and 
            reanalyzed.get('confidence', 0) > 0.7):
            
            errors.append({
                'type': 'number_mismatch',
                'rectangle_id': rect_analysis.get('rectangle_id'),
                'original_number': detected_number,
                'suggested_number': best_reanalyzed,
                'confidence': reanalyzed.get('confidence'),
                'message': f"Numéro détecté '{detected_number}' différent de la re-analyse '{best_reanalyzed}'"
            })
        
        return errors
    
    def _suggest_visual_corrections(self, analysis: Dict, rectangles: List[Dict]) -> List[Dict]:
        """
        Propose des corrections basées sur l'analyse visuelle
        """
        corrections = []
        
        for error in analysis.get('visual_errors', []):
            if error['type'] == 'number_mismatch':
                corrections.append({
                    'type': 'visual_correction',
                    'rectangle_id': error['rectangle_id'],
                    'original_number': error['original_number'],
                    'corrected_number': error['suggested_number'],
                    'confidence': error['confidence'],
                    'method': 'visual_reanalysis',
                    'reason': f"Re-analyse visuelle suggère '{error['suggested_number']}' au lieu de '{error['original_number']}'"
                })
        
        return corrections
    
    def create_visual_correction_report(self, extraction_dir: str) -> Dict:
        """
        Crée un rapport de correction visuelle pour toute l'extraction
        """
        extraction_path = Path(extraction_dir)
        
        report = {
            'extraction_dir': str(extraction_path),
            'analysis_date': str(np.datetime64('now')),
            'pages_analyzed': 0,
            'total_rectangles': 0,
            'visual_errors_found': 0,
            'corrections_suggested': 0,
            'pages_details': {},
            'summary_corrections': []
        }
        
        # Analyser chaque page
        for page_dir in extraction_path.glob('page_*'):
            if page_dir.is_dir():
                page_num = int(page_dir.name.split('_')[1])
                page_analysis = self.analyze_page_images(page_dir)
                
                if 'error' not in page_analysis:
                    report['pages_details'][page_num] = page_analysis
                    report['pages_analyzed'] += 1
                    report['total_rectangles'] += len(page_analysis.get('rectangles_analysis', []))
                    report['visual_errors_found'] += len(page_analysis.get('visual_errors', []))
                    report['corrections_suggested'] += len(page_analysis.get('suggested_corrections', []))
                    
                    # Collecter les corrections
                    report['summary_corrections'].extend(page_analysis.get('suggested_corrections', []))
        
        return report


def main():
    """Fonction principale pour tester le correcteur visuel"""
    print("👁️ CORRECTEUR VISUEL DUBUFFET")
    print("=" * 50)
    
    corrector = DubuffetVisualCorrector()
    
    # Analyser le répertoire d'extraction fourni
    extraction_dir = input("📁 Chemin du répertoire d'extraction (ou Entrée pour exemple): ").strip()
    
    if not extraction_dir:
        # Utiliser l'exemple fourni
        extraction_dir = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-VIII_ULTRA_20250910_142409"
    
    if not os.path.exists(extraction_dir):
        print(f"❌ Répertoire non trouvé: {extraction_dir}")
        return
    
    print(f"\n👁️ Analyse visuelle de: {extraction_dir}")
    
    # Créer le rapport de correction visuelle
    report = corrector.create_visual_correction_report(extraction_dir)
    
    print(f"\n📊 RAPPORT D'ANALYSE VISUELLE:")
    print(f"   - Pages analysées: {report['pages_analyzed']}")
    print(f"   - Rectangles analysés: {report['total_rectangles']}")
    print(f"   - Erreurs visuelles détectées: {report['visual_errors_found']}")
    print(f"   - Corrections suggérées: {report['corrections_suggested']}")
    
    # Afficher les corrections suggérées
    if report['summary_corrections']:
        print(f"\n🔧 CORRECTIONS VISUELLES SUGGÉRÉES:")
        for i, correction in enumerate(report['summary_corrections'], 1):
            print(f"   {i}. {correction['reason']}")
            print(f"      Confiance: {correction['confidence']:.2f}")
    
    # Sauvegarder le rapport
    output_file = Path(extraction_dir) / 'visual_correction_report.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ Rapport visuel sauvegardé: {output_file}")


if __name__ == "__main__":
    main()
