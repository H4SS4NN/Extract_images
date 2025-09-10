#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROCESSEUR COMPLET DUBUFFET
Combine l'extraction d'images + OCR des légendes + génération JSON final
Format identique à Picasso avec toutes les œuvres et leurs images liées
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from datetime import datetime

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import Logger
from dubuffet_ocr_extractor import DubuffetOCRExtractor

# Configuration du logger
complete_logger = logging.getLogger("dubuffet_complete")
complete_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
complete_logger.addHandler(handler)

class DubuffetCompleteProcessor:
    """
    Processeur complet pour Dubuffet : extraction + OCR + JSON final
    """
    
    def __init__(self):
        self.logger = Logger("DubuffetComplete")
        self.ocr_extractor = DubuffetOCRExtractor()
        
    def find_extraction_directories(self, base_dir: str = "extractions_ultra") -> List[str]:
        """Trouve tous les répertoires d'extraction Dubuffet"""
        extraction_dirs = []
        base_path = Path(base_dir)
        
        if not base_path.exists():
            self.logger.warning(f"Répertoire {base_dir} introuvable")
            return []
            
        for item in base_path.iterdir():
            if item.is_dir() and "DUBUFFET" in item.name.upper():
                extraction_dirs.append(str(item))
                
        return sorted(extraction_dirs)
    
    def load_page_images(self, page_dir: Path) -> Dict[str, Dict]:
        """Charge toutes les images extraites d'une page"""
        images_info = {}
        
        # Charger les détails ultra si disponibles
        ultra_details_file = page_dir / "page_ultra_details.json"
        if ultra_details_file.exists():
            try:
                with open(ultra_details_file, 'r', encoding='utf-8') as f:
                    ultra_data = json.load(f)
                    
                # Parcourir les détections d'images
                for detection in ultra_data.get("detections", []):
                    img_file = detection.get("image_file")
                    if img_file and (page_dir / img_file).exists():
                        img_path = page_dir / img_file
                        images_info[img_file] = {
                            "path": str(img_path),
                            "bbox": detection.get("bbox", {}),
                            "confidence": detection.get("confidence", 0.0),
                            "size": detection.get("size", {}),
                            "detected_number": detection.get("detected_number"),
                            "method": "ultra_detector"
                        }
            except Exception as e:
                self.logger.warning(f"Erreur lecture ultra_details page {page_dir.name}: {e}")
        
        # Fallback: scanner les fichiers image directement
        if not images_info:
            for img_file in page_dir.glob("*.png"):
                if img_file.name != "page_full_image.jpg":
                    images_info[img_file.name] = {
                        "path": str(img_file),
                        "bbox": {},
                        "confidence": 0.0,
                        "size": {},
                        "detected_number": None,
                        "method": "file_scan"
                    }
                    
        return images_info
    
    def link_artwork_to_images(self, artwork_data: Dict, page_images: Dict[str, Dict]) -> List[Dict]:
        """Lie une œuvre OCR avec ses images correspondantes"""
        linked_images = []
        artwork_index = artwork_data.get("index")
        
        # Si on a un index, chercher les images correspondantes
        if artwork_index is not None:
            for img_name, img_info in page_images.items():
                detected_num = img_info.get("detected_number")
                
                # Correspondance exacte par numéro
                if detected_num == artwork_index:
                    linked_images.append({
                        "filename": img_name,
                        "path": img_info["path"],
                        "bbox": img_info["bbox"],
                        "confidence": img_info["confidence"],
                        "size": img_info["size"],
                        "match_method": "exact_number",
                        "match_confidence": 1.0
                    })
                    
        # Si pas de correspondance exacte, prendre toutes les images de la page
        if not linked_images and page_images:
            for img_name, img_info in page_images.items():
                linked_images.append({
                    "filename": img_name,
                    "path": img_info["path"],
                    "bbox": img_info["bbox"],
                    "confidence": img_info["confidence"],
                    "size": img_info["size"],
                    "match_method": "page_fallback",
                    "match_confidence": 0.5
                })
                
        return linked_images
    
    def process_extraction_directory(self, extraction_dir: str) -> Dict:
        """Traite un répertoire d'extraction complet"""
        extraction_path = Path(extraction_dir)
        
        if not extraction_path.exists():
            self.logger.error(f"Répertoire d'extraction introuvable: {extraction_dir}")
            return {}
            
        complete_logger.info(f"🎨 Traitement complet Dubuffet: {extraction_path.name}")
        
        # 1. Exécuter l'OCR sur toutes les pages
        ocr_results = self.ocr_extractor.process_extraction_directory(extraction_dir)
        
        # 2. Construire le JSON final au format Picasso
        final_json = {
            "extraction_info": {
                "extraction_dir": str(extraction_path),
                "collection": "Jean Dubuffet",
                "processing_date": datetime.now().isoformat(),
                "total_pages": 0,
                "total_artworks": 0,
                "extraction_method": "dubuffet_complete_processor"
            },
            "artworks": {},
            "pages_summary": {}
        }
        
        # 3. Parcourir toutes les pages et lier images + OCR
        page_dirs = [d for d in extraction_path.iterdir() if d.is_dir() and d.name.startswith("page_")]
        page_dirs.sort(key=lambda x: int(x.name.split("_")[1]))
        
        artwork_counter = 1
        
        for page_dir in page_dirs:
            page_num = int(page_dir.name.split("_")[1])
            complete_logger.info(f"📄 Traitement page {page_num}")
            
            # Charger les images de la page
            page_images = self.load_page_images(page_dir)
            
            # Récupérer les œuvres OCR de cette page
            page_artworks = []
            if "pages" in ocr_results:
                for page_data in ocr_results["pages"]:
                    if page_data.get("page_number") == page_num and page_data.get("found_caption"):
                        for item in page_data.get("items", []):
                            page_artworks.append(item)
            
            # Créer les entrées d'œuvres finales
            page_summary = {
                "page_number": page_num,
                "images_found": len(page_images),
                "captions_found": len(page_artworks),
                "artworks": []
            }
            
            if page_artworks:
                # Lier chaque œuvre OCR avec ses images
                for artwork in page_artworks:
                    artwork_id = f"artwork_{artwork_counter:03d}"
                    linked_images = self.link_artwork_to_images(artwork, page_images)
                    
                    final_artwork = {
                        "id": artwork_id,
                        "index": artwork.get("index"),
                        "title": artwork.get("title"),
                        "medium": artwork.get("medium"),
                        "dimensions_cm": artwork.get("dimensions_cm", {"width": None, "height": None}),
                        "date_text": artwork.get("date_text"),
                        "date_iso": artwork.get("date_iso"),
                        "approximate": artwork.get("approximate", False),
                        "page": page_num,
                        "ocr_region": artwork.get("region"),
                        "ocr_confidence": artwork.get("confidence_mean", 0.0),
                        "ocr_text_raw": artwork.get("ocr_text_raw", ""),
                        "images": linked_images,
                        "extraction_method": "dubuffet_complete"
                    }
                    
                    final_json["artworks"][artwork_id] = final_artwork
                    page_summary["artworks"].append(artwork_id)
                    artwork_counter += 1
                    
            else:
                # Pas d'OCR, mais on peut avoir des images détectées
                if page_images:
                    for img_name, img_info in page_images.items():
                        artwork_id = f"artwork_{artwork_counter:03d}"
                        
                        final_artwork = {
                            "id": artwork_id,
                            "index": img_info.get("detected_number"),
                            "title": None,
                            "medium": None,
                            "dimensions_cm": {"width": None, "height": None},
                            "date_text": None,
                            "date_iso": None,
                            "approximate": False,
                            "page": page_num,
                            "ocr_region": None,
                            "ocr_confidence": 0.0,
                            "ocr_text_raw": "",
                            "images": [{
                                "filename": img_name,
                                "path": img_info["path"],
                                "bbox": img_info["bbox"],
                                "confidence": img_info["confidence"],
                                "size": img_info["size"],
                                "match_method": "image_only",
                                "match_confidence": 0.8
                            }],
                            "extraction_method": "image_detection_only"
                        }
                        
                        final_json["artworks"][artwork_id] = final_artwork
                        page_summary["artworks"].append(artwork_id)
                        artwork_counter += 1
            
            final_json["pages_summary"][f"page_{page_num:03d}"] = page_summary
            
        # Mettre à jour les statistiques finales
        final_json["extraction_info"]["total_pages"] = len(page_dirs)
        final_json["extraction_info"]["total_artworks"] = len(final_json["artworks"])
        
        # Sauvegarder le JSON final
        output_file = extraction_path / "dubuffet_complete_catalog.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
            
        complete_logger.info(f"✅ Catalogue complet sauvegardé: {output_file}")
        complete_logger.info(f"📊 {final_json['extraction_info']['total_artworks']} œuvres sur {final_json['extraction_info']['total_pages']} pages")
        
        return final_json
    
    def process_all_dubuffet_extractions(self, base_dir: str = "extractions_ultra") -> List[Dict]:
        """Traite toutes les extractions Dubuffet trouvées"""
        extraction_dirs = self.find_extraction_directories(base_dir)
        
        if not extraction_dirs:
            complete_logger.warning("Aucune extraction Dubuffet trouvée")
            return []
            
        results = []
        for extraction_dir in extraction_dirs:
            complete_logger.info(f"🎯 Traitement: {Path(extraction_dir).name}")
            result = self.process_extraction_directory(extraction_dir)
            if result:
                results.append(result)
                
        return results

def main():
    """Point d'entrée principal"""
    print("🎨 PROCESSEUR COMPLET DUBUFFET")
    print("=" * 50)
    
    processor = DubuffetCompleteProcessor()
    
    # Traiter toutes les extractions Dubuffet
    results = processor.process_all_dubuffet_extractions()
    
    if results:
        print(f"\n✅ {len(results)} extractions traitées avec succès!")
        
        # Afficher un résumé
        total_artworks = sum(r["extraction_info"]["total_artworks"] for r in results)
        total_pages = sum(r["extraction_info"]["total_pages"] for r in results)
        
        print(f"📊 RÉSUMÉ GLOBAL:")
        print(f"   - Extractions: {len(results)}")
        print(f"   - Pages totales: {total_pages}")
        print(f"   - Œuvres totales: {total_artworks}")
        
        # Afficher les détails par extraction
        for result in results:
            info = result["extraction_info"]
            print(f"\n🎨 {Path(info['extraction_dir']).name}:")
            print(f"   - Pages: {info['total_pages']}")
            print(f"   - Œuvres: {info['total_artworks']}")
            print(f"   - Fichier: dubuffet_complete_catalog.json")
    else:
        print("❌ Aucune extraction trouvée ou traitée")

if __name__ == "__main__":
    main()
