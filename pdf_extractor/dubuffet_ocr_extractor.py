#!/usr/bin/env python3
"""
Extracteur OCR spécialisé pour les catalogues Dubuffet
Basé sur les spécifications pour extraire les légendes d'œuvres
"""

import re
import cv2
import numpy as np
import logging
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import pytesseract
from pytesseract import Output
import sys

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from utils import logger

# Configuration du logger OCR
ocr_logger = logging.getLogger("dubuffet_ocr")
ocr_logger.setLevel(logging.DEBUG)  # Activé pour voir tous les détails

# Configuration Tesseract
TESS_PSM_PARA = "--oem 3 --psm 6 -l fra"
TESS_PSM_LINE = "--oem 3 --psm 7 -l fra"

# Dictionnaire des mois français
MONTHS = {
    "janvier": "01", "février": "02", "fevrier": "02", "mars": "03",
    "avril": "04", "mai": "05", "juin": "06", "juillet": "07",
    "août": "08", "aout": "08", "septembre": "09", "octobre": "10",
    "novembre": "11", "décembre": "12", "decembre": "12"
}

@dataclass
class Caption:
    """Structure pour une légende d'œuvre"""
    index: Optional[int]
    title: Optional[str]
    medium: Optional[str]
    width_cm: Optional[int]
    height_cm: Optional[int]
    date_text: Optional[str]
    date_iso: Optional[str]
    approximate: bool
    region: str
    ocr_text_raw: str
    confidence_mean: float

class DubuffetOCRExtractor:
    """
    Extracteur OCR spécialisé pour les catalogues Dubuffet
    """
    
    def __init__(self):
        self.logger = logger
        self._configure_tesseract()
    
    def _configure_tesseract(self):
        """Configure Tesseract OCR avec les mêmes chemins que le système principal"""
        import pytesseract
        from config import TESSERACT_PATHS
        
        for path in TESSERACT_PATHS:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                self.logger.info(f"✅ Tesseract OCR configuré: {path}")
                return True
        
        self.logger.warning("⚠️ Tesseract non trouvé pour l'OCR Dubuffet")
        return False
        
    def _auto_artwork_bbox(self, page_bgr: np.ndarray) -> Optional[Tuple[int,int,int,int]]:
        """Détection automatique de la bbox de l'œuvre"""
        H, W = page_bgr.shape[:2]
        gray = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2GRAY)
        # fond blanc -> on inverse pour faire ressortir l'œuvre
        inv = cv2.bitwise_not(gray)
        thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        # nettoyage
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (11,11))
        clean = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, k, iterations=2)
        cnts, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts: 
            return None
        # on prend le plus grand contour raisonnable (< 95% de la page)
        areas = [(cv2.contourArea(c), c) for c in cnts]
        areas.sort(reverse=True, key=lambda x: x[0])
        for area, c in areas:
            if area < 0.95*W*H:
                x,y,w,h = cv2.boundingRect(c)
                # on contraint un peu pour éviter de prendre toute la page
                pad = int(0.01*min(W,H))
                return max(0,x+pad), max(0,y+pad), min(W,x+w-pad), min(H,y+h-pad)
        return None

    def _preprocess_image(self, gray: np.ndarray) -> np.ndarray:
        """Préprocessing optimisé pour les légendes Dubuffet"""
        # Améliorer le contraste
        gray = cv2.convertScaleAbs(gray, alpha=1.3, beta=10)
        
        # Binarisation adaptative
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9
        )
        
        return binary
    
    def _ocr_with_fallbacks(self, prep, region_name):
        """OCR avec plusieurs configurations de fallback"""
        configs = [TESS_PSM_PARA, "--oem 3 --psm 4 -l fra", "--oem 3 --psm 11 -l fra"]
        best = ("", 0.0, None)

        for cfg in configs:
            try:
                data = pytesseract.image_to_data(prep, lang="fra", config=cfg, output_type=Output.DICT)
                text = pytesseract.image_to_string(prep, lang="fra", config=cfg)
                confs = [int(c) for c in data["conf"] if c != '-1']
                conf_mean = float(np.mean(confs)) if confs else 0.0
                if conf_mean > best[1]:
                    best = (text, conf_mean, data)
            except Exception as e:
                self.logger.debug(f"Erreur OCR config {cfg}: {e}")
                continue
        return best
    
    def ocr_region(self, img: np.ndarray, region_name: str, y0: int, y1: int, 
                   x0: int, x1: int, save_debug: bool = False, 
                   debug_prefix: str = "debug") -> Tuple[str, List[str], float, Optional[np.ndarray]]:
        """
        Applique l'OCR sur une région spécifique de l'image
        """
        h, w = img.shape[:2]
        y0, y1 = max(0, y0), min(h, y1)
        x0, x1 = max(0, x0), min(w, x1)
        
        if y0 >= y1 or x0 >= x1:
            return "", [], 0.0, None
            
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return "", [], 0.0, None
        
        # Préprocessing
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        prep = self._preprocess_image(gray)
        
        # upscale si petit texte
        if min(prep.shape[:2]) < 500:
            prep = cv2.resize(prep, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        # Sauvegarder pour debug si demandé
        if save_debug:
            debug_file = f"{debug_prefix}_{region_name}.png"
            cv2.imwrite(debug_file, prep)
            self.logger.debug(f"Debug image sauvée: {debug_file}")
        
        try:
            # OCR + fallbacks
            text, conf_mean, data = self._ocr_with_fallbacks(prep, region_name)
            nums = re.findall(r"(?<!\d)(\d{1,3})(?!\d)", text)
            
            # Logger les résultats
            ocr_logger.info("🗂️  Zone %-8s | conf≈%.1f | nums=%s", region_name, conf_mean, nums)
            ocr_logger.info("    Texte: %s", " ".join(text.split()))
            
            # Sauvegarder le texte pour debug
            if save_debug:
                with open(f"{debug_prefix}_{region_name}.txt", "w", encoding="utf-8") as f:
                    f.write(text)
            
            return text, nums, conf_mean, crop
            
        except Exception as e:
            self.logger.error(f"Erreur OCR région {region_name}: {e}")
            return "", [], 0.0, crop
    
    def parse_caption_text(self, raw: str) -> Tuple[Optional[int], Optional[str], Optional[str], 
                                                   Optional[int], Optional[int], Optional[str], 
                                                   Optional[str], bool]:
        """
        Parse le texte OCR pour extraire les informations de la légende
        """
        # Normaliser le texte
        t = " ".join(raw.replace("×", "x").replace("X", "x").split())
        
        # 1. Index + titre en majuscules (regex plus robuste)
        m1 = re.search(r"(?<!\d)(\d{1,3})\s+([A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ''\- ]{3,})", t)
        idx = int(m1.group(1)) if m1 else None
        title = m1.group(2).strip(" .") if m1 else None
        
        # 2. Médium (liste étendue pour Dubuffet)
        medium_pattern = (
            r"(huile sur toile|gouache sur papier|gouache|encre sur papier|encre|"
            r"crayon|acrylique|tempera|pastel|collage|technique mixte|"
            r"pâte battue|matière|assemblage)"
        )
        m2 = re.search(medium_pattern, t, re.IGNORECASE)
        medium = m2.group(1).lower() if m2 else None
        
        # 3. Dimensions
        m3 = re.search(r"(\d{1,3})\s*[xX×]\s*(\d{1,3})\s*cm", t)
        wcm = int(m3.group(1)) if m3 else None
        hcm = int(m3.group(2)) if m3 else None
        
        # 4. Date
        approx = bool(re.search(r"\b(vers|circa|env\.)\b", t, re.IGNORECASE))
        
        # Pattern pour dates françaises
        date_pattern = (
            r"(vers\s+le\s+)?(?:(\d{1,2})\s+)?"
            r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|"
            r"août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})"
        )
        m4 = re.search(date_pattern, t, re.IGNORECASE)
        
        date_txt = None
        date_iso = None
        if m4:
            date_txt = m4.group(0).strip(" .")
            day = m4.group(2)
            month = MONTHS.get(m4.group(3).lower())
            year = m4.group(4)
            
            if month:
                if day:
                    date_iso = f"{year}-{month}-{int(day):02d}"
                else:
                    date_iso = f"{year}-{month}"
            else:
                date_iso = year
        
        return idx, title, medium, wcm, hcm, date_txt, date_iso, approx
    
    def parse_multiple_captions(self, raw: str) -> List[Dict]:
        """Parse multiple captions from the same text block"""
        t = " ".join(raw.replace("×","x").replace("X","x").split())
        # points de départ possibles de légende: " 5 PAYSAGE ..." " 6 LA ..."
        starts = [m.start() for m in re.finditer(r"(?<!\d)\d{1,3}\s+[A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ''\- ]{3,}", t)]
        if not starts:
            # essayer quand même en unique
            idx, title, medium, wcm, hcm, date_txt, date_iso, approx = self.parse_caption_text(t)
            return [] if not (idx or title or medium or (wcm and hcm)) else [{
                "index": idx, "title": title, "medium": medium,
                "dimensions_cm": {"width": wcm, "height": hcm},
                "date_text": date_txt, "date_iso": date_iso, "approximate": approx
            }]

        starts.append(len(t))
        items = []
        for i in range(len(starts)-1):
            seg = t[starts[i]:starts[i+1]]
            idx, title, medium, wcm, hcm, date_txt, date_iso, approx = self.parse_caption_text(seg)
            if (idx or title or medium or (wcm and hcm)):
                items.append({
                    "index": idx, "title": title, "medium": medium,
                    "dimensions_cm": {"width": wcm, "height": hcm},
                    "date_text": date_txt, "date_iso": date_iso, "approximate": approx
                })
        return items
    
    def extract_caption_from_page(self, page_bgr: np.ndarray,
                                  artwork_bbox: Optional[Tuple[int, int, int, int]] = None,
                                  band_px: int = 260,
                                  save_debug: bool = True,
                                  debug_prefix: str = "debug_page") -> Dict:
        """
        Extrait la légende d'une page Dubuffet en analysant les zones autour de l'œuvre
        """
        H, W = page_bgr.shape[:2]

        # 1) BBox de l'œuvre
        if artwork_bbox:
            x0, y0, x1, y1 = artwork_bbox
        else:
            auto_bbox = self._auto_artwork_bbox(page_bgr)
            if auto_bbox:
                x0, y0, x1, y1 = auto_bbox
            else:
                # heuristique "centrée"
                x0, y0 = int(0.07*W), int(0.18*H)
                x1, y1 = int(0.93*W), int(0.83*H)

        # 2) Bandes dynamiques réduites pour éviter de capturer plusieurs titres
        v_band = max(int(0.08*H), 180)   # vertical réduit (top/bottom) 
        h_band = max(int(0.10*W), 200)   # horizontal réduit (left/right)

        regions = {
            "top":    (y0 - v_band, y0 - 1,     max(0, x0 - int(0.02*W)), min(W, x1 + int(0.02*W))),
            "bottom": (y1 + 1,      y1 + v_band, max(0, x0 - int(0.02*W)), min(W, x1 + int(0.02*W))),
            "left":   (max(0, y0 - int(0.02*H)), min(H, y1 + int(0.02*H)), x0 - h_band, x0 - 1),
            "right":  (max(0, y0 - int(0.02*H)), min(H, y1 + int(0.02*H)), x1 + 1, x1 + h_band)
        }
        
        collected = []
        
        # Analyser chaque région
        for region_name, (yy0, yy1, xx0, xx1) in regions.items():
            raw_text, nums, conf, crop = self.ocr_region(
                page_bgr, region_name, yy0, yy1, xx0, xx1, save_debug, debug_prefix
            )

            if not raw_text.strip():
                continue

            # NEW: multi-légendes possibles
            items = self.parse_multiple_captions(raw_text)
            for it in items:
                it["region"] = region_name
                it["ocr_text_raw"] = " ".join(raw_text.split())
                it["confidence_mean"] = round(conf, 1)
                score = (40 if it.get("index") else 0) + (30 if it.get("medium") else 0) + \
                       (20 if (it["dimensions_cm"]["width"] and it["dimensions_cm"]["height"]) else 0) + \
                       int(conf/2)
                collected.append((score, it))
                
                ocr_logger.info(
                    "➡️  Region %-8s | score=%d | idx=%s | title=%s | medium=%s | dim=%sx%s | date=%s",
                    region_name, score, it.get("index"), it.get("title"), it.get("medium"), 
                    it["dimensions_cm"].get("width"), it["dimensions_cm"].get("height"), it.get("date_text")
                )

        # dédoublonner par index (on garde le meilleur score)
        by_idx = {}
        for score, it in collected:
            key = it.get("index") or f"noindex_{it['region']}"
            if key not in by_idx or score > by_idx[key][0]:
                by_idx[key] = (score, it)

        final_items = [v[1] for v in by_idx.values()]
        final_items.sort(key=lambda x: (x.get("index") or 9999))

        result = {
            "found_caption": len(final_items) > 0,
            "best_region": max(collected, key=lambda p: p[0])[1]["region"] if collected else None,
            "all_regions_analyzed": len(regions),
            "items": final_items
        }
        
        return result
    
    def process_extraction_directory(self, extraction_dir: str) -> Dict:
        """
        Traite tout un répertoire d'extraction Dubuffet
        """
        extraction_path = Path(extraction_dir)
        if not extraction_path.exists():
            self.logger.error(f"❌ Répertoire non trouvé: {extraction_dir}")
            return {}
        
        self.logger.info(f"🎨 Traitement OCR Dubuffet: {extraction_path.name}")
        
        results = {
            "extraction_dir": str(extraction_path),
            "collection": "Jean Dubuffet",
            "total_pages": 0,
            "captions_found": 0,
            "artworks": {},
            "processing_log": []
        }
        
        # Traiter chaque page
        for page_dir in sorted(extraction_path.glob('page_*')):
            if page_dir.is_dir():
                page_num = int(page_dir.name.split('_')[1])
                results["total_pages"] += 1
                
                # Charger l'image complète de la page
                full_image_path = page_dir / 'page_full_image.jpg'
                if not full_image_path.exists():
                    self.logger.warning(f"Image complète manquante pour page {page_num}")
                    continue
                
                page_image = cv2.imread(str(full_image_path))
                if page_image is None:
                    self.logger.error(f"Impossible de charger l'image page {page_num}")
                    continue
                
                # Extraire la légende
                debug_prefix = str(page_dir / f"ocr_debug_page_{page_num}")
                caption_result = self.extract_caption_from_page(
                    page_image, save_debug=True, debug_prefix=debug_prefix
                )
                
                # Traiter les résultats
                if caption_result["found_caption"]:
                    results["captions_found"] += 1
                    
                    for item in caption_result["items"]:
                        artwork_key = str(item["index"])
                        results["artworks"][artwork_key] = {
                            **item,
                            "page": page_num,
                            "extraction_method": "dubuffet_ocr"
                        }
                
                # Logger le traitement
                log_entry = {
                    "page": page_num,
                    "caption_found": caption_result["found_caption"],
                    "best_region": caption_result.get("best_region"),
                    "items_count": len(caption_result["items"])
                }
                results["processing_log"].append(log_entry)
                
                self.logger.info(
                    f"📄 Page {page_num}: {'✅' if caption_result['found_caption'] else '❌'} "
                    f"({caption_result.get('best_region', 'aucune')})"
                )
        
        return results


def main():
    """Fonction principale pour tester l'extracteur OCR"""
    print("📝 EXTRACTEUR OCR DUBUFFET")
    print("=" * 50)
    
    extractor = DubuffetOCRExtractor()
    
    # Demander le répertoire d'extraction
    extraction_dir = input("📁 Chemin du répertoire d'extraction: ").strip()
    
    if not extraction_dir:
        extraction_dir = "extractions_ultra/DUBUFFET-JEAN_LIEUX-MOMENTANES-PATES-BATTUES-VIII_ULTRA_20250910_142409"
    
    if not os.path.exists(extraction_dir):
        print(f"❌ Répertoire non trouvé: {extraction_dir}")
        return
    
    # Traitement OCR
    results = extractor.process_extraction_directory(extraction_dir)
    
    # Affichage des résultats
    print(f"\n📊 RÉSULTATS OCR:")
    print(f"   - Pages traitées: {results['total_pages']}")
    print(f"   - Légendes trouvées: {results['captions_found']}")
    print(f"   - Œuvres identifiées: {len(results['artworks'])}")
    
    # Afficher les œuvres trouvées
    if results['artworks']:
        print(f"\n🎨 ŒUVRES IDENTIFIÉES:")
        for idx, artwork in results['artworks'].items():
            title = artwork.get('title', 'Sans titre')
            medium = artwork.get('medium', 'Technique inconnue')
            dims = artwork.get('dimensions_cm', {})
            date = artwork.get('date_text', 'Date inconnue')
            
            print(f"   {idx}. {title}")
            print(f"      {medium} - {dims.get('width', '?')}×{dims.get('height', '?')} cm")
            print(f"      {date} (page {artwork.get('page')})")
    
    # Sauvegarder les résultats
    output_file = Path(extraction_dir) / 'dubuffet_ocr_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Résultats sauvegardés: {output_file}")


if __name__ == "__main__":
    main()
