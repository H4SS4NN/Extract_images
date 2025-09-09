#!/usr/bin/env python3
"""
Générateur de JSON final pour les images extraites
Combine les images, numéros d'œuvres et informations du sommaire
"""

import json
import os
import uuid
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class FinalJSONGenerator:
    """Générateur de JSON final pour l'interface web"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        
    def generate_final_json(self, session_data: Dict, output_dir: str) -> Dict:
        """Génère le JSON final pour toutes les images extraites"""
        logger.info("🎯 Génération du JSON final...")
        
        # Collecter toutes les informations
        all_artworks = []
        summary_data = self._collect_summary_data(session_data)
        
        # Parcourir toutes les pages
        for page_data in session_data.get('pages', []):
            page_num = page_data.get('page_number', 0)
            page_dir = page_data.get('page_dir', '')
            
            if not page_dir or not os.path.exists(page_dir):
                continue
                
            # Récupérer les rectangles détectés
            rectangles_details = page_data.get('rectangles_details', [])
            
            for rect in rectangles_details:
                artwork_json = self._create_artwork_json(rect, page_num, page_dir, summary_data)
                if artwork_json:
                    all_artworks.append(artwork_json)
        
        # Créer le JSON final
        final_data = {
            "session_info": {
                "pdf_name": session_data.get('pdf_name', ''),
                "total_images": len(all_artworks),
                "extraction_date": session_data.get('start_time', ''),
                "mode": "ULTRA_SENSIBLE"
            },
            "artworks": all_artworks
        }
        
        # Sauvegarder le JSON final
        final_json_path = os.path.join(output_dir, "final_artworks.json")
        with open(final_json_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 JSON final sauvegardé: {final_json_path}")
        logger.info(f"📊 {len(all_artworks)} œuvres traitées")
        
        return final_data
    
    def _collect_summary_data(self, session_data: Dict) -> Dict:
        """Collecte toutes les données de sommaires"""
        summary_data = {}
        
        for page_data in session_data.get('pages', []):
            summary_analysis = page_data.get('summary_analysis', {})
            
            if summary_analysis.get('is_summary') and summary_analysis.get('entries'):
                for entry in summary_analysis['entries']:
                    artwork_number = entry.get('artwork_number')
                    if artwork_number:
                        summary_data[artwork_number] = entry
        
        logger.info(f"📋 {len(summary_data)} entrées de sommaire collectées")
        return summary_data
    
    def _create_artwork_json(self, rect: Dict, page_num: int, page_dir: str, summary_data: Dict) -> Optional[Dict]:
        """Crée le JSON final pour une œuvre"""
        try:
            # Informations de base
            artwork_number = rect.get('artwork_number')
            filename = rect.get('filename', '')
            is_doubtful = rect.get('is_doubtful', False)
            
            # Chemin de l'image
            image_path = os.path.join(page_dir, filename)
            if not os.path.exists(image_path):
                logger.warning(f"Image non trouvée: {image_path}")
                return None
            
            # URL de l'image (pour l'interface web)
            image_url = f"{self.base_url}/images/{os.path.basename(page_dir)}/{filename}"
            
            # Informations du sommaire si disponible
            summary_info = summary_data.get(artwork_number) if artwork_number else {}
            
            # Créer l'ID unique
            artwork_id = str(uuid.uuid4())
            
            # Dimensions de l'image
            try:
                import cv2
                img = cv2.imread(image_path)
                if img is not None:
                    height, width = img.shape[:2]
                    image_size = [width, height]  # [largeur, hauteur]
                else:
                    image_size = [0, 0]
            except:
                image_size = [0, 0]
            
            # JSON final
            artwork_json = {
                "artist_name": summary_info.get('artist_name'),
                "title": summary_info.get('title'),
                "id": artwork_id,
                "image_url": image_url,
                "image_path": image_path,
                "image_filename": filename,
                "size": summary_info.get('size'),
                "size_unit": summary_info.get('size_unit'),
                "medium": summary_info.get('medium'),
                "signature": summary_info.get('signature'),
                "execution_year": summary_info.get('execution_year'),
                "description": summary_info.get('description'),
                "provenance": summary_info.get('provenance', []),
                "literature": summary_info.get('literature', []),
                "exhibition": summary_info.get('exhibition', []),
                "metadata": {
                    "artwork_number": artwork_number,
                    "page_number": page_num,
                    "is_doubtful": is_doubtful,
                    "confidence": rect.get('confidence', 0.0),
                    "detection_method": rect.get('detection_method', 'unknown'),
                    "image_dimensions": image_size,
                    "extraction_method": summary_info.get('extraction_method', 'unknown'),
                    "raw_text": summary_info.get('raw_text', ''),
                    "bbox": rect.get('bbox', {}),
                    "area": rect.get('area', 0)
                }
            }
            
            # Ajouter des informations spécifiques si c'est une image douteuse
            if is_doubtful:
                artwork_json["metadata"]["doubt_reasons"] = rect.get('doubt_reasons', [])
                artwork_json["metadata"]["quality_analysis"] = {
                    "is_doubtful": True,
                    "confidence": rect.get('confidence', 0.0),
                    "reasons": rect.get('doubt_reasons', [])
                }
            
            return artwork_json
            
        except Exception as e:
            logger.error(f"Erreur création JSON pour {filename}: {e}")
            return None
    
    def create_individual_jsons(self, final_data: Dict, output_dir: str):
        """Crée des fichiers JSON individuels pour chaque œuvre"""
        artworks_dir = os.path.join(output_dir, "individual_artworks")
        os.makedirs(artworks_dir, exist_ok=True)
        
        for artwork in final_data.get('artworks', []):
            artwork_id = artwork.get('id', 'unknown')
            artwork_file = os.path.join(artworks_dir, f"{artwork_id}.json")
            
            with open(artwork_file, 'w', encoding='utf-8') as f:
                json.dump(artwork, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 {len(final_data.get('artworks', []))} fichiers JSON individuels créés")
    
    def create_summary_report(self, final_data: Dict, output_dir: str):
        """Crée un rapport de synthèse"""
        report_path = os.path.join(output_dir, "extraction_report.md")
        
        artworks = final_data.get('artworks', [])
        session_info = final_data.get('session_info', {})
        
        # Statistiques
        total_images = len(artworks)
        doubtful_images = len([a for a in artworks if a.get('metadata', {}).get('is_doubtful', False)])
        with_summary = len([a for a in artworks if a.get('artist_name')])
        
        # Groupes par numéro d'œuvre
        by_number = {}
        for artwork in artworks:
            num = artwork.get('metadata', {}).get('artwork_number')
            if num:
                if num not in by_number:
                    by_number[num] = []
                by_number[num].append(artwork)
        
        # Créer le rapport
        report = f"""# RAPPORT D'EXTRACTION FINAL

## 📊 Statistiques Générales
- **PDF**: {session_info.get('pdf_name', 'N/A')}
- **Date d'extraction**: {session_info.get('extraction_date', 'N/A')}
- **Mode**: {session_info.get('mode', 'N/A')}
- **Total d'images**: {total_images}
- **Images douteuses**: {doubtful_images}
- **Images avec informations sommaire**: {with_summary}

## 🎯 Images par Numéro d'Œuvre
"""
        
        for num in sorted(by_number.keys()):
            artworks_for_num = by_number[num]
            report += f"\n### Numéro {num} ({len(artworks_for_num)} image(s))\n"
            
            for artwork in artworks_for_num:
                title = artwork.get('title', 'Sans titre')
                artist = artwork.get('artist_name', 'Artiste inconnu')
                filename = artwork.get('image_filename', 'N/A')
                is_doubtful = artwork.get('metadata', {}).get('is_doubtful', False)
                doubtful_mark = " ⚠️" if is_doubtful else ""
                
                report += f"- **{filename}**: {artist}, {title}{doubtful_mark}\n"
        
        report += f"""
## 📁 Fichiers Générés
- `final_artworks.json`: JSON complet avec toutes les œuvres
- `individual_artworks/`: Dossier avec un JSON par œuvre
- `extraction_report.md`: Ce rapport

## 🔗 Utilisation
Les fichiers JSON peuvent être utilisés directement dans une interface web.
Chaque œuvre contient:
- Informations artistiques (artiste, titre, dimensions, etc.)
- Chemin et URL de l'image
- Métadonnées d'extraction
- Informations de qualité
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"📄 Rapport de synthèse créé: {report_path}")

