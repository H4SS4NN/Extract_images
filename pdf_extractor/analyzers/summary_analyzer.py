#!/usr/bin/env python3
"""
Analyseur de sommaires pour catalogues d'art
Utilise Mistral pour extraire et structurer les informations d'œuvres
"""

import json
import re
import logging
import requests
import os
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)

class SummaryAnalyzer:
    """Analyseur de sommaires pour extraire les informations d'œuvres d'art"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", mistral_model: str = "mistral"):
        self.ollama_url = ollama_url
        self.mistral_model = mistral_model
        self.mistral_enabled = self._check_mistral_availability()
        
        # Configuration pour la détection des sommaires
        self.summary_patterns = [
            r"sommaire",
            r"table\s+des\s+matières",
            r"index",
            r"catalogue",
            r"œuvres",
            r"plates?",
            r"figures?"
        ]
        
        # Patterns pour détecter les numéros d'œuvres dans les sommaires
        self.artwork_number_patterns = [
            r"(\d+)\s*[\.\)]\s*",  # "1. " ou "1) "
            r"n[o°]?\s*(\d+)",     # "n° 1" ou "no 1"
            r"plate\s*(\d+)",      # "plate 1"
            r"fig\.?\s*(\d+)",     # "fig. 1"
            r"(\d+)\s*[–-]\s*",    # "1 - " ou "1 – "
        ]
    
    def _check_mistral_availability(self) -> bool:
        """Vérifie si Mistral est disponible via Ollama"""
        try:
            # Vérifier si Ollama est en cours d'exécution
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                
                # Chercher un modèle Mistral
                mistral_models = [name for name in model_names if 'mistral' in name.lower()]
                if mistral_models:
                    logger.info(f"✅ Mistral local disponible: {mistral_models[0]}")
                    self.mistral_model = mistral_models[0]  # Utiliser le premier modèle Mistral trouvé
                    return True
                else:
                    logger.warning("⚠️ Ollama disponible mais aucun modèle Mistral trouvé")
                    logger.info("💡 Pour installer Mistral: ollama pull mistral")
                    return False
            else:
                logger.warning(f"⚠️ Erreur Ollama: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Ollama non disponible: {e}")
            logger.info("💡 Pour installer Ollama: https://ollama.ai/")
            return False
    
    def _query_mistral(self, prompt: str, image_base64: str = None) -> Optional[str]:
        """Interroge le modèle Mistral via Ollama"""
        if not self.mistral_enabled:
            return None
        
        try:
            # Ollama utilise un format différent
            payload = {
                "model": self.mistral_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000
                }
            }
            
            # Si une image est fournie, l'ajouter (Ollama supporte les images)
            if image_base64:
                payload["images"] = [image_base64]
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60  # Plus de temps pour les modèles locaux
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                logger.error(f"Erreur Ollama Mistral: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur requête Ollama Mistral: {e}")
            return None
    
    def detect_summary_page(self, page_text: str) -> bool:
        """Détecte si une page contient un sommaire"""
        page_text_lower = page_text.lower()
        
        # Vérifier les patterns de sommaire
        for pattern in self.summary_patterns:
            if re.search(pattern, page_text_lower):
                return True
        
        # Vérifier la présence de numéros suivis de texte (caractéristique des sommaires)
        number_text_lines = 0
        lines = page_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) > 10:  # Ligne suffisamment longue
                # Vérifier si la ligne commence par un numéro suivi de texte
                for pattern in self.artwork_number_patterns:
                    if re.match(pattern, line):
                        number_text_lines += 1
                        break
        
        # Si plus de 3 lignes avec numéro + texte, probablement un sommaire
        return number_text_lines >= 3
    
    def extract_artwork_entries(self, page_text: str) -> List[Dict]:
        """Extrait les entrées d'œuvres du sommaire"""
        entries = []
        lines = page_text.split('\n')
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if len(line) < 5:  # Ignorer les lignes trop courtes
                continue
            
            # Chercher un numéro d'œuvre au début de la ligne
            artwork_number = None
            for pattern in self.artwork_number_patterns:
                match = re.match(pattern, line)
                if match:
                    artwork_number = int(match.group(1))
                    break
            
            if artwork_number:
                # Extraire le texte après le numéro
                text_after_number = re.sub(r'^\d+[\.\)\s]*', '', line).strip()
                
                if text_after_number:
                    entries.append({
                        'line_number': line_num + 1,
                        'artwork_number': artwork_number,
                        'raw_text': text_after_number,
                        'full_line': line
                    })
        
        return entries
    
    def analyze_artwork_entry(self, entry: Dict, page_image: np.ndarray = None) -> Dict:
        """Analyse une entrée d'œuvre avec l'aide de Mistral"""
        artwork_number = entry['artwork_number']
        raw_text = entry['raw_text']
        
        # Prompt pour Mistral
        prompt = f"""Analyse ce texte d'une entrée de catalogue d'art et extrais les informations structurées.

Numéro d'œuvre: {artwork_number}
Texte brut: "{raw_text}"

Extrais et structure les informations suivantes au format JSON:
{{
    "artist_name": "Nom de l'artiste",
    "title": "Titre de l'œuvre",
    "medium": "Technique utilisée (huile sur toile, etc.)",
    "size": [largeur, hauteur],
    "size_unit": "cm ou in",
    "execution_year": année,
    "signature": true/false,
    "description": "Description complète",
    "provenance": ["Provenance 1", "Provenance 2"],
    "literature": ["Référence littéraire 1"],
    "exhibition": ["Exposition 1"],
    "confidence": 0.0-1.0
}}

Règles:
- Si une information n'est pas claire, utilise null
- Pour les dimensions, extrais les nombres et l'unité
- Pour l'année, cherche 4 chiffres consécutifs
- Pour la signature, cherche "signé", "signed", "sig."
- Structure le JSON proprement
- Évalue la confiance de l'extraction (0.0-1.0)

Réponds UNIQUEMENT avec le JSON, sans autre texte."""

        # Si une image est fournie, l'utiliser pour l'analyse
        image_base64 = None
        if page_image is not None:
            try:
                _, buffer = cv2.imencode('.jpg', page_image)
                image_base64 = buffer.tobytes().decode('base64')
            except:
                pass
        
        # Interroger Mistral
        mistral_response = self._query_mistral(prompt, image_base64)
        
        if mistral_response:
            try:
                # Parser la réponse JSON
                structured_data = json.loads(mistral_response)
                
                # Ajouter les métadonnées
                structured_data['artwork_number'] = artwork_number
                structured_data['raw_text'] = raw_text
                structured_data['line_number'] = entry['line_number']
                structured_data['extraction_method'] = 'mistral'
                
                return structured_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Erreur parsing JSON Mistral: {e}")
                logger.error(f"Réponse reçue: {mistral_response}")
        
        # Fallback: extraction basique sans IA
        return self._extract_basic_info(entry)
    
    def _extract_basic_info(self, entry: Dict) -> Dict:
        """Extraction basique sans IA (fallback)"""
        raw_text = entry['raw_text']
        
        # Extraction basique avec regex
        artist_name = None
        title = None
        medium = None
        size = None
        size_unit = None
        execution_year = None
        signature = False
        
        # Chercher l'artiste (généralement au début)
        artist_patterns = [
            r"^([A-Z][a-z]+ [A-Z][a-z]+)",  # "Nom Prénom"
            r"^([A-Z][a-z]+)",  # "Nom"
        ]
        
        for pattern in artist_patterns:
            match = re.search(pattern, raw_text)
            if match:
                artist_name = match.group(1)
                break
        
        # Chercher le titre (après l'artiste, avant la virgule)
        if artist_name:
            title_match = re.search(rf"{re.escape(artist_name)},\s*([^,]+)", raw_text)
            if title_match:
                title = title_match.group(1).strip()
        
        # Chercher les dimensions
        size_patterns = [
            r"(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*(cm|in|m)",  # "100 x 80 cm"
            r"(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*(centimètres|inches|mètres)",  # "100 x 80 centimètres"
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                size = [float(match.group(1)), float(match.group(2))]
                size_unit = match.group(3).lower()
                if size_unit in ['centimètres', 'centimètre']:
                    size_unit = 'cm'
                elif size_unit in ['inches', 'inch']:
                    size_unit = 'in'
                elif size_unit in ['mètres', 'mètre']:
                    size_unit = 'm'
                break
        
        # Chercher l'année
        year_match = re.search(r'\b(19|20)\d{2}\b', raw_text)
        if year_match:
            execution_year = int(year_match.group(0))
        
        # Chercher la signature
        signature_patterns = [r'signé', r'signed', r'sig\.', r'signature']
        for pattern in signature_patterns:
            if re.search(pattern, raw_text, re.IGNORECASE):
                signature = True
                break
        
        return {
            'artwork_number': entry['artwork_number'],
            'raw_text': raw_text,
            'line_number': entry['line_number'],
            'artist_name': artist_name,
            'title': title,
            'medium': medium,
            'size': size,
            'size_unit': size_unit,
            'execution_year': execution_year,
            'signature': signature,
            'description': raw_text,
            'provenance': [],
            'literature': [],
            'exhibition': [],
            'confidence': 0.3,  # Faible confiance pour extraction basique
            'extraction_method': 'regex_fallback'
        }
    
    def analyze_summary_page(self, page_text: str, page_image: np.ndarray = None) -> Dict:
        """Analyse complète d'une page de sommaire"""
        logger.info("🔍 Analyse du sommaire...")
        
        # Détecter si c'est un sommaire
        is_summary = self.detect_summary_page(page_text)
        if not is_summary:
            return {
                'is_summary': False,
                'message': 'Page ne semble pas être un sommaire'
            }
        
        # Extraire les entrées d'œuvres
        entries = self.extract_artwork_entries(page_text)
        logger.info(f"📋 {len(entries)} entrées d'œuvres trouvées")
        
        if not entries:
            return {
                'is_summary': True,
                'entries': [],
                'message': 'Aucune entrée d\'œuvre trouvée'
            }
        
        # Analyser chaque entrée
        analyzed_entries = []
        for entry in entries:
            logger.info(f"  🔍 Analyse entrée {entry['artwork_number']}...")
            analyzed_entry = self.analyze_artwork_entry(entry, page_image)
            analyzed_entries.append(analyzed_entry)
        
        return {
            'is_summary': True,
            'entries': analyzed_entries,
            'total_entries': len(analyzed_entries),
            'mistral_enabled': self.mistral_enabled,
            'extraction_method': 'mistral' if self.mistral_enabled else 'regex_fallback'
        }
    
    def create_artwork_json(self, analyzed_entry: Dict) -> str:
        """Crée un JSON structuré pour une œuvre"""
        # Créer un ID unique basé sur le numéro d'œuvre
        artwork_id = f"artwork-{analyzed_entry['artwork_number']:03d}"
        
        # Structure finale
        artwork_data = {
            "artist_name": analyzed_entry.get('artist_name'),
            "title": analyzed_entry.get('title'),
            "id": artwork_id,
            "image_url": None,  # Sera rempli plus tard
            "size": analyzed_entry.get('size'),
            "size_unit": analyzed_entry.get('size_unit'),
            "medium": analyzed_entry.get('medium'),
            "signature": analyzed_entry.get('signature'),
            "execution_year": analyzed_entry.get('execution_year'),
            "description": analyzed_entry.get('description'),
            "provenance": analyzed_entry.get('provenance', []),
            "literature": analyzed_entry.get('literature', []),
            "exhibition": analyzed_entry.get('exhibition', []),
            "metadata": {
                "artwork_number": analyzed_entry['artwork_number'],
                "raw_text": analyzed_entry['raw_text'],
                "line_number": analyzed_entry['line_number'],
                "extraction_method": analyzed_entry.get('extraction_method', 'unknown'),
                "confidence": analyzed_entry.get('confidence', 0.0)
            }
        }
        
        return json.dumps(artwork_data, indent=2, ensure_ascii=False)
    
    def save_summary_analysis(self, analysis: Dict, output_path: str):
        """Sauvegarde l'analyse du sommaire"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Analyse du sommaire sauvegardée: {output_path}")
        
        # Créer aussi des fichiers individuels pour chaque œuvre
        if analysis.get('is_summary') and analysis.get('entries'):
            base_dir = os.path.dirname(output_path)
            artworks_dir = os.path.join(base_dir, "artworks")
            os.makedirs(artworks_dir, exist_ok=True)
            
            for entry in analysis['entries']:
                artwork_json = self.create_artwork_json(entry)
                artwork_file = os.path.join(artworks_dir, f"artwork_{entry['artwork_number']:03d}.json")
                
                with open(artwork_file, 'w', encoding='utf-8') as f:
                    f.write(artwork_json)
                
                logger.info(f"  💾 Œuvre {entry['artwork_number']} sauvegardée: {artwork_file}")
