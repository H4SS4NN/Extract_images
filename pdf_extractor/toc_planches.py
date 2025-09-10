#!/usr/bin/env python3
"""
Module for detecting and parsing TABLE DES PLANCHES from PDF documents.
Extracts plate numbers, titles, and page references for image renaming.
"""

import re
import json
import os
import unicodedata
import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    import cv2
    import numpy as np
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cache pour éviter de recharger le même PDF
_toc_cache = {}


def extract_toc_from_pdf(pdf_path: str, last_n: int = 10) -> Optional[Dict]:
    """
    Extract TABLE DES PLANCHES from the last N pages of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        last_n: Number of last pages to search (default: 10)
        
    Returns:
        Dictionary with plates data or None if not found
    """
    try:
        print(f"🔍 DEBUG: pdf_path = {pdf_path} (type: {type(pdf_path)})")
        print(f"🔍 DEBUG: last_n = {last_n} (type: {type(last_n)})")
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        # Vérifier que c'est bien un PDF
        if pdf_path.suffix.lower() != '.pdf':
            logger.error(f"File is not a PDF: {pdf_path}")
            return None
        
        # Vérifier le cache
        cache_key = f"{pdf_path}_{last_n}"
        if cache_key in _toc_cache:
            logger.debug(f"TOC trouvé dans le cache pour {pdf_path}")
            return _toc_cache[cache_key]
            
        logger.info(f"🔍 Recherche TABLE DES PLANCHES dans les {last_n} dernières pages...")
        logger.debug(f"PDF path: {pdf_path}")
        logger.debug(f"PDF exists: {pdf_path.exists()}")
        
        # Try text layer extraction first
        logger.debug("Tentative extraction via couche texte...")
        toc_data = _extract_from_text_layer(pdf_path, last_n)
        if toc_data:
            logger.info(f"✅ TABLE DES PLANCHES trouvée via couche texte (page {toc_data['source_page_index'] + 1})")
            # Sauvegarder dans le cache
            _toc_cache[cache_key] = toc_data
            return toc_data
            
        # Fallback to OCR if text layer is insufficient
        if TESSERACT_AVAILABLE:
            logger.info("📄 Tentative OCR sur les dernières pages...")
            logger.debug("Tentative extraction via OCR...")
            toc_data = _extract_from_ocr(pdf_path, last_n)
            if toc_data:
                logger.info(f"✅ TABLE DES PLANCHES trouvée via OCR (page {toc_data['source_page_index'] + 1})")
                # Sauvegarder dans le cache
                _toc_cache[cache_key] = toc_data
                return toc_data
        else:
            logger.debug("Tesseract non disponible - pas de fallback OCR")
        
        logger.warning("⚠️ TABLE DES PLANCHES non trouvée dans les dernières pages")
        # Mettre None dans le cache pour éviter de retenter
        _toc_cache[cache_key] = None
        return None
        
    except Exception as e:
        import traceback
        print(f"❌ TRACEBACK COMPLET:")
        print(traceback.format_exc())
        logger.error(f"❌ Erreur lors de l'extraction TOC: {e}")
        logger.debug(f"Exception type: {type(e).__name__}")
        logger.debug(f"Exception details: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return None


def extract_toc_from_pdf_multipage(pdf_path: str, last_n: int = 15, keywords: List[str] = None) -> Optional[Dict]:
    """
    Extract TABLE DES PLANCHES with multi-page support.
    Cherche plus de pages et combine les résultats.
    """
    try:
        logger.debug(f"🔍 DEBUG: extract_toc_from_pdf_multipage appelé avec:")
        logger.debug(f"   - pdf_path: {pdf_path}")
        logger.debug(f"   - last_n: {last_n}")
        logger.debug(f"   - keywords: {keywords}")
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"❌ PDF file not found: {pdf_path}")
            return None
            
        logger.info(f"🔍 Recherche TABLE DES PLANCHES dans les {last_n} dernières pages (mode multi-page)...")
        logger.debug(f"📋 Mots-clés utilisés: {keywords if keywords else 'Mots-clés par défaut (Picasso)'}")
        
        all_plates = []
        toc_found = False
        source_pages = []
        
        # Essayer d'abord la couche texte
        logger.debug(f"📖 PDFPLUMBER_AVAILABLE: {PDFPLUMBER_AVAILABLE}")
        if PDFPLUMBER_AVAILABLE:
            try:
                logger.debug("🔍 Tentative d'extraction avec pdfplumber...")
                with pdfplumber.open(pdf_path) as pdf:
                    total_pages = len(pdf.pages)
                    start_page = max(0, total_pages - last_n)
                    logger.debug(f"📄 PDF: {total_pages} pages, recherche dans pages {start_page+1} à {total_pages}")
                    
                    for i in range(total_pages - 1, start_page - 1, -1):
                        logger.debug(f"🔍 Analyse page {i+1}/{total_pages}")
                        page = pdf.pages[i]
                        text = page.extract_text()
                        
                        logger.debug(f"📄 Page {i+1}: Texte extrait = {len(text) if text else 0} caractères")
                        if text and len(text.strip()) >= 50:
                            # Afficher un échantillon du texte pour debug
                            sample_text = text.strip()[:200] + "..." if len(text) > 200 else text.strip()
                            logger.debug(f"📝 Échantillon texte page {i+1}: {sample_text}")
                            
                            # Créer un dossier temporaire pour le debug
                            import tempfile
                            with tempfile.TemporaryDirectory() as temp_dir:
                                logger.debug(f"🔍 Analyse du texte avec keywords: {keywords}")
                                toc_data = parse_toc_text(text, temp_dir, keywords)
                                if toc_data:
                                    logger.info(f"✅ TABLE DES PLANCHES trouvée sur page {i+1}!")
                                    page_plates = toc_data['plates']
                                    all_plates.extend(page_plates)
                                    source_pages.append(i)
                                    toc_found = True
                                else:
                                    logger.debug(f"❌ Aucun sommaire détecté sur page {i+1}")
                        else:
                            logger.debug(f"⏭️ Page {i+1} ignorée (texte trop court: {len(text) if text else 0} caractères)")
            except Exception as e:
                logger.error(f"❌ pdfplumber multi-page failed: {e}")
                logger.debug(f"📋 Exception details: {str(e)}")
                
                # Erreurs communes avec pdfplumber
                if "PSLiteral" in str(e) and "float" in str(e):
                    logger.warning("⚠️ Erreur pdfplumber PSLiteral - PDF mal formaté, passage au fallback PyMuPDF")
                elif "timeout" in str(e).lower():
                    logger.warning("⚠️ Timeout pdfplumber - PC trop lent, passage au fallback")
                else:
                    import traceback
                    logger.debug(f"📋 Traceback: {traceback.format_exc()}")
        
        if toc_found:
            # Trier par numéro de planche
            all_plates.sort(key=lambda x: x['number'])
            
            # Supprimer les doublons
            unique_plates = []
            seen_numbers = set()
            for plate in all_plates:
                if plate['number'] not in seen_numbers:
                    unique_plates.append(plate)
                    seen_numbers.add(plate['number'])
            
            logger.info(f"✅ SOMMAIRE COMPLET: {len(unique_plates)} planches uniques détectées")
            logger.info(f"📄 Pages source: {[p+1 for p in sorted(source_pages)]}")
            logger.info(f"🔢 Numéros: {min(seen_numbers)} à {max(seen_numbers)}")
            
            return {
                "plates": unique_plates,
                "source_page_index": source_pages[0] if source_pages else 0,
                "all_source_pages": source_pages,
                "total_plates": len(unique_plates)
            }
        
        logger.warning("⚠️ TABLE DES PLANCHES non trouvée")
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction TOC multi-page: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return None


def _extract_from_text_layer(pdf_path: Path, last_n: int) -> Optional[Dict]:
    """Extract TOC using text layer (pdfplumber or PyMuPDF)"""
    
    # Try pdfplumber first
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                start_page = max(0, total_pages - last_n)
                
                for i in range(total_pages - 1, start_page - 1, -1):  # Search from end
                    page = pdf.pages[i]
                    text = page.extract_text()
                    
                    if text and len(text.strip()) >= 50:  # Minimum text length
                        toc_data = parse_toc_text(text, keywords=keywords)
                        if toc_data:
                            toc_data['source_page_index'] = i
                            return toc_data
        except Exception as e:
            logger.debug(f"pdfplumber failed: {e}")
    
    # Try PyMuPDF as fallback
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            start_page = max(0, total_pages - last_n)
            
            for i in range(total_pages - 1, start_page - 1, -1):  # Search from end
                page = doc[i]
                text = page.get_text()
                
                if text and len(text.strip()) >= 50:  # Minimum text length
                    toc_data = parse_toc_text(text, keywords=keywords)
                    if toc_data:
                        toc_data['source_page_index'] = i
                        doc.close()
                        return toc_data
            
            doc.close()
        except Exception as e:
            logger.debug(f"PyMuPDF failed: {e}")
    
    return None


def _extract_from_ocr(pdf_path: Path, last_n: int) -> Optional[Dict]:
    """Extract TOC using OCR on page images"""
    
    try:
        # Check Tesseract availability
        _ = pytesseract.get_tesseract_version()
    except Exception:
        logger.warning("⚠️ Tesseract non disponible - OCR désactivé")
        return None
    
    try:
        # CORRECTION: Obtenir le nombre total de pages avec PyPDF2
        import PyPDF2
        with open(str(pdf_path), 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        # Calculer les pages à traiter
        start_page = max(1, total_pages - last_n + 1)
        end_page = total_pages
        
        logger.debug(f"OCR: Conversion pages {start_page}-{end_page} sur {total_pages} total")
        
        # Convertir seulement les pages nécessaires
        pages = convert_from_path(
            str(pdf_path), 
            first_page=start_page, 
            last_page=end_page,
            dpi=200  # DPI réduit pour économiser la mémoire
        )
        
        # Traiter de la dernière vers la première
        for i in range(len(pages) - 1, -1, -1):
            page_image = pages[i]
            page_array = np.array(page_image)
            page_cv = cv2.cvtColor(page_array, cv2.COLOR_RGB2BGR)
            
            # OCR with optimized config for text
            gray = cv2.cvtColor(page_cv, cv2.COLOR_BGR2GRAY)
            
            # Preprocessing for better OCR
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Scale up for better OCR
            big = cv2.resize(enhanced, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            
            text = pytesseract.image_to_string(big, config='--psm 6')
            
            if text and len(text.strip()) >= 50:  # Minimum text length
                toc_data = parse_toc_text(text, keywords=keywords)
                if toc_data:
                    # Ajuster l'index de page pour correspondre au PDF original
                    actual_page_index = start_page + i - 1
                    toc_data['source_page_index'] = actual_page_index
                    logger.debug(f"TOC trouvé via OCR sur page PDF {actual_page_index + 1}")
                    return toc_data
                    
    except Exception as e:
        logger.error(f"❌ Erreur OCR: {e}")
    
    return None


def parse_toc_text(raw_text: str, debug_output_dir: str = None, keywords: List[str] = None) -> Optional[Dict]:
    """
    Parse TABLE DES PLANCHES from raw text with improved multi-page support.
    
    Args:
        raw_text: Raw text content from PDF page
        debug_output_dir: Directory to save debug info
        
    Returns:
        Dictionary with parsed plates data or None if not found
    """
    if not raw_text or len(raw_text.strip()) < 50:
        logger.debug(f"❌ parse_toc_text: Texte trop court ({len(raw_text) if raw_text else 0} caractères)")
        return None
    
    logger.debug(f"🔍 parse_toc_text: Analyse d'un texte de {len(raw_text)} caractères")
    logger.debug(f"📝 Premiers 300 caractères: {raw_text[:300]}")
    
    # Normalize text for matching
    normalized_text = unicodedata.normalize('NFKD', raw_text).encode('ascii', 'ignore').decode()
    logger.debug(f"🔤 Texte normalisé: {len(normalized_text)} caractères")
    
    # Detect TABLE DES PLANCHES heading (plus flexible)
    # Utiliser les mots-clés personnalisés si fournis
    if keywords:
        logger.debug(f"🔍 Utilisation des mots-clés personnalisés: {keywords}")
        heading_patterns = []
        for keyword in keywords:
            # Créer des patterns flexibles pour chaque mot-clé
            escaped_keyword = re.escape(keyword.upper())
            heading_patterns.extend([
                rf'^\s*{escaped_keyword}\s*$',
                rf'^\s*{escaped_keyword}\s*\d{{4}}\s*$',  # Avec année
                rf'{escaped_keyword}',  # Plus permissif
            ])
    else:
        logger.debug("🔍 Utilisation des patterns par défaut (Picasso)")
        # Patterns par défaut (Picasso)
        heading_patterns = [
            r'^\s*TABLE\s+DES\s+PLANCHES\s*$',
            r'^\s*TABLE\s+DES\s+PLANCHES\s*\d{4}\s*$',  # Avec année
            r'TABLE\s+DES\s+PLANCHES',  # Plus permissif
        ]
    
    logger.debug(f"🔍 Test de {len(heading_patterns)} patterns de titre")
    heading_match = None
    for i, pattern in enumerate(heading_patterns):
        logger.debug(f"🔍 Pattern {i+1}: {pattern}")
        heading_match = re.search(pattern, normalized_text, re.IGNORECASE | re.MULTILINE)
        if heading_match:
            logger.debug(f"✅ Match trouvé avec pattern {i+1}: {heading_match.group()}")
            break
        else:
            logger.debug(f"❌ Pas de match avec pattern {i+1}")
    
    if not heading_match:
        # Vérifier si on est dans une page de continuation du sommaire
        # Si on trouve des patterns comme "1 TÊTE DE FEMME" ou "187 HOMME"
        continuation_pattern = r'^\s*\d+\s+[A-ZÁÊÈ].*?\.{2,}\s*\d+\s*$'
        if re.search(continuation_pattern, normalized_text, re.MULTILINE):
            logger.info("📋 Page de continuation du sommaire détectée")
            content_text = raw_text.strip()
        else:
            return None
    else:
        logger.info("📋 En-tête TABLE DES PLANCHES détectée")
        # Extract text after the heading
        heading_end = heading_match.end()
        content_text = raw_text[heading_end:].strip()
    
    if not content_text:
        return None
    
    # Parse plate entries with improved patterns
    plates = _parse_plate_entries_improved(content_text, debug_output_dir)
    
    if not plates:
        logger.warning("⚠️ Aucune entrée de planche trouvée")
        return None
    
    logger.info(f"📊 {len(plates)} planches détectées sur cette page")
    
    return {
        "plates": plates,
        "source_page_index": 0  # Will be set by caller
    }


def _parse_plate_entries_improved(content_text: str, debug_output_dir: str = None) -> List[Dict]:
    """Parse individual plate entries with improved patterns and debug output"""
    plates = []
    lines = content_text.split('\n')
    
    # NOUVEAUX PATTERNS plus robustes basés sur vos images
    patterns = [
        # Pattern principal: "1 TÊTE DE FEMME. Dessin à l'encre et au crayon. 1er janvier 1969. 41 × 31.5 cm. .................... 1"
        r'^\s*(\d+)\s+([A-ZÁÊÈÏÔÙÇ][A-ZÁÊÈÏÔÙÇa-zàâäéèêëïîôùûüÿç\s\',.-]+?)\..*?\.{2,}\s*(\d+)\s*$',
        
        # Pattern avec numéro et titre seulement: "1 TÊTE DE FEMME. Dessin à l'encre..."
        r'^\s*(\d+)\s+([A-ZÁÊÈÏÔÙÇ][A-ZÁÊÈÏÔÙÇa-zàâäéèêëïîôùûüÿç\s\',.-]+?)\..*$',
        
        # Pattern simplifié: "187 HOMME À L'ÉPÉE"
        r'^\s*(\d+)\s+([A-ZÁÊÈÏÔÙÇ][A-ZÁÊÈÏÔÙÇa-zàâäéèêëïîôùûüÿç\s\',.-]+?)\s*\..*',
        
        # Pattern très permissif pour rattraper les cas limites
        r'^\s*(\d+)\s+([A-ZÁÊÈ][^.]*?)\..*'
    ]
    
    debug_info = []
    
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 5:
            continue
            
        matched = False
        for pattern_idx, pattern in enumerate(patterns):
            match = re.match(pattern, line_clean, re.IGNORECASE)
            if match:
                try:
                    number = int(match.group(1))
                    title_raw = match.group(2).strip()
                    
                    # Nettoyer le titre (enlever les descriptions techniques)
                    title = _clean_title(title_raw)
                    
                    # Chercher le numéro de page si présent
                    page = None
                    if len(match.groups()) >= 3:
                        try:
                            page = int(match.group(3))
                        except (ValueError, IndexError):
                            pass
                    
                    plates.append({
                        "number": number,
                        "title": title,
                        "page": page,
                        "raw_line": line_clean,
                        "pattern_used": pattern_idx
                    })
                    
                    debug_info.append(f"✅ Ligne {i+1}: #{number} '{title}' (page {page}) [Pattern {pattern_idx}]")
                    matched = True
                    break
                    
                except (ValueError, IndexError) as e:
                    debug_info.append(f"❌ Ligne {i+1}: Erreur parsing - {e}")
                    continue
        
        if not matched and len(line_clean) > 10:
            debug_info.append(f"⚠️ Ligne {i+1}: Non reconnue - '{line_clean[:50]}...'")
    
    # Sauvegarder les infos de debug
    if debug_output_dir and debug_info:
        debug_file = os.path.join(debug_output_dir, "sommaire_parsing_debug.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write("ANALYSE DU PARSING DU SOMMAIRE\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total lignes analysées: {len(lines)}\n")
            f.write(f"Planches détectées: {len(plates)}\n\n")
            f.write("DÉTAIL PAR LIGNE:\n")
            for info in debug_info:
                f.write(f"{info}\n")
            f.write(f"\nPLANCHES EXTRAITES:\n")
            for plate in plates:
                f.write(f"#{plate['number']:3d}: {plate['title']} (page {plate['page']})\n")
        
        logger.info(f"💾 Debug parsing sauvegardé: {debug_file}")
    
    return plates


def _clean_title(title_raw: str) -> str:
    """Nettoie le titre en enlevant les détails techniques"""
    # Enlever les descriptions techniques après le premier point
    title = title_raw.split('.')[0].strip()
    
    # Enlever les caractères de fin indésirables
    title = re.sub(r'[,\-\s]*$', '', title)
    
    # Limiter la longueur
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title


def _parse_plate_entries(content_text: str) -> List[Dict]:
    """Parse individual plate entries from content text (legacy function)"""
    return _parse_plate_entries_improved(content_text)


def build_plate_map(toc_json: Dict) -> Dict[int, Dict]:
    """
    Build a mapping from plate numbers to title and page info.
    
    Args:
        toc_json: TOC data from extract_toc_from_pdf
        
    Returns:
        Dictionary mapping plate numbers to title/page info
    """
    if not toc_json or 'plates' not in toc_json:
        return {}
    
    plate_map = {}
    for plate in toc_json['plates']:
        number = plate['number']
        plate_map[number] = {
            'title': plate['title'],
            'page': plate['page'],
            'raw_line': plate.get('raw_line', '')
        }
    
    return plate_map


def slugify(s: str) -> str:
    """
    Create a URL-safe slug from a string.
    
    Args:
        s: Input string
        
    Returns:
        ASCII-only, lowercase, dash-separated slug
    """
    if not s:
        return ""
    
    # Normalize unicode
    s = unicodedata.normalize('NFKD', s)
    
    # Convert to lowercase and replace spaces with dashes
    s = s.lower().strip()
    
    # Remove punctuation except dashes and alphanumeric
    s = re.sub(r'[^\w\s-]', '', s)
    
    # Replace multiple spaces/dashes with single dash
    s = re.sub(r'[-\s]+', '-', s)
    
    # Remove leading/trailing dashes
    s = s.strip('-')
    
    # Limit length
    if len(s) > 50:
        s = s[:50].rstrip('-')
    
    return s


def save_toc_json(toc_data: Dict, output_dir) -> Path:
    """Save TOC data to JSON file"""
    output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
    json_path = output_dir / "sommaire_planches.json"
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(toc_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Sommaire sauvegardé: {json_path}")
        return json_path
        
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde sommaire: {e}")
        return None


def load_toc_json(json_path) -> Optional[Dict]:
    """Load TOC data from JSON file"""
    try:
        json_path = Path(json_path) if isinstance(json_path, str) else json_path
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Erreur chargement sommaire: {e}")
        return None


def apply_renaming(output_dir, plate_map: Dict[int, Dict], 
                  detections_data: Dict) -> Dict[str, int]:
    """
    Apply renaming to extracted images based on plate mapping.
    
    Args:
        output_dir: Directory containing extracted images
        plate_map: Mapping from plate numbers to title/page info
        detections_data: Data about detected plate numbers per image
        
    Returns:
        Statistics about renaming operation
    """
    output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
    
    stats = {
        'total_images': 0,
        'renamed': 0,
        'skipped': 0,
        'not_matched': 0
    }
    
    if not plate_map:
        logger.warning("⚠️ Aucune correspondance de planches disponible")
        return stats
    
    logger.info("🔄 Application du renommage...")
    
    # Collect all images with detected numbers
    images_to_rename = []
    
    for page_dir in output_dir.glob("page_*"):
        if not page_dir.is_dir():
            continue
            
        for image_file in page_dir.glob("*.png"):
            if image_file.name.startswith("thumb_"):
                continue
                
            # Extract detected number from filename or detections data
            detected_number = _extract_number_from_filename(image_file.name)
            if detected_number is None:
                continue
                
            images_to_rename.append({
                'file': image_file,
                'number': detected_number,
                'original_name': image_file.name
            })
            stats['total_images'] += 1
    
    # Apply renaming
    for item in images_to_rename:
        number = item['number']
        image_file = item['file']
        
        if number not in plate_map:
            logger.warning(f"⚠️ Planche {number} non trouvée dans le sommaire")
            stats['not_matched'] += 1
            continue
        
        plate_info = plate_map[number]
        new_name = _generate_new_filename(number, plate_info, image_file.suffix)
        
        if new_name == image_file.name:
            stats['skipped'] += 1
            continue
        
        # Handle collisions
        new_path = image_file.parent / new_name
        collision_suffix = 1
        while new_path.exists():
            name_part = new_name.rsplit('.', 1)[0]
            ext_part = new_name.rsplit('.', 1)[1] if '.' in new_name else ''
            new_name = f"{name_part}_v{collision_suffix}.{ext_part}" if ext_part else f"{name_part}_v{collision_suffix}"
            new_path = image_file.parent / new_name
            collision_suffix += 1
        
        try:
            # Rename main image
            image_file.rename(new_path)
            
            # Rename thumbnail if exists
            thumb_file = image_file.parent / f"thumb_{image_file.name}"
            if thumb_file.exists():
                thumb_new_name = f"thumb_{new_name}"
                thumb_new_path = image_file.parent / thumb_new_name
                thumb_file.rename(thumb_new_path)
            
            logger.info(f"✅ {item['original_name']} → {new_name}")
            stats['renamed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Erreur renommage {image_file.name}: {e}")
            stats['skipped'] += 1
    
    return stats


def _extract_number_from_filename(filename: str) -> Optional[int]:
    """Extract plate number from filename"""
    # Try to extract number from filename patterns
    patterns = [
        r'^(\d+)\.png$',  # "1.png"
        r'^(\d+)_',       # "1_title.png"
        r'^rectangle_(\d+)',  # "rectangle_01.png"
    ]
    
    for pattern in patterns:
        match = re.match(pattern, filename)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    
    return None


def _generate_new_filename(number: int, plate_info: Dict, extension: str) -> str:
    """Generate new filename based on plate info"""
    title = plate_info.get('title', '')
    page = plate_info.get('page')
    
    slug = slugify(title)
    if not slug:
        slug = f"planche-{number}"
    
    if page is not None:
        return f"{number:03d}_{slug}_{page:03d}{extension}"
    else:
        return f"{number:03d}_{slug}{extension}"


def _extract_artwork_details_from_line(raw_line: str) -> Dict[str, str]:
    """
    Extrait les détails d'une œuvre depuis la ligne complète du sommaire.
    
    Args:
        raw_line: Ligne complète du sommaire (ex: "1 TÊTE DE FEMME. Dessin à l'encre et au crayon. ler janvier 1969. 44 × 31,5 cm. 1")
        
    Returns:
        Dictionnaire avec medium, execution_year, size_from_sommaire
    """
    import re
    
    details = {
        "medium": "No comment",
        "execution_year": "No comment", 
        "size_from_sommaire": "No comment"
    }
    
    if not raw_line:
        return details
    
    # Extraire le medium (après le titre, avant la date)
    # Pattern: "TITRE. Medium description. Date..."
    # Exemple: "1 TÊTE DE FEMME. Dessin à l'encre et au crayon. ler janvier 1969"
    medium_match = re.search(r'\.\s*([^.]*?)\s*\.\s*(?:ler\s+\w+\s+\d{4}|\d{4})', raw_line)
    if medium_match:
        details["medium"] = medium_match.group(1).strip()
    
    # Extraire l'année (format: "ler janvier 1969" ou "1969")
    year_match = re.search(r'(\d{4})', raw_line)
    if year_match:
        details["execution_year"] = year_match.group(1)
    
    # Extraire les dimensions (format: "44 × 31,5 cm" ou "44 x 31.5 cm")
    size_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*[×x]\s*(\d+(?:[,\.]\d+)?)\s*cm', raw_line, re.IGNORECASE)
    if size_match:
        width = size_match.group(1).replace(',', '.')
        height = size_match.group(2).replace(',', '.')
        details["size_from_sommaire"] = f"{width} x {height} cm"
    
    return details


def create_artwork_json(image_path: Path, plate_number: int, plate_info: Dict, 
                       artist_name: str, image_size: tuple) -> Dict:
    """
    Crée un JSON d'œuvre d'art basé sur les informations du sommaire.
    
    Args:
        image_path: Chemin vers l'image
        plate_number: Numéro de la planche
        plate_info: Informations de la planche depuis le sommaire
        artist_name: Nom de l'artiste (depuis le nom du PDF)
        image_size: Taille de l'image (width, height) en pixels
        
    Returns:
        Dictionnaire JSON de l'œuvre
    """
    import uuid
    
    # Générer un ID unique
    artwork_id = str(uuid.uuid4())
    
    # Extraire le titre depuis le sommaire
    title = plate_info.get('title', f'Œuvre {plate_number}')
    
    # Extraire les détails depuis la ligne complète
    raw_line = plate_info.get('raw_line', '')
    logger.info(f"🔍 Raw line pour planche {plate_number}: '{raw_line}'")
    details = _extract_artwork_details_from_line(raw_line)
    logger.info(f"🔍 Détails extraits: {details}")
    
    # Utiliser les dimensions du sommaire si disponibles, sinon calculer depuis l'image
    if details["size_from_sommaire"] != "No comment":
        size_cm = details["size_from_sommaire"]
        # Extraire width et height pour le format JSON
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)', size_cm)
        if size_match:
            width_cm = float(size_match.group(1))
            height_cm = float(size_match.group(2))
        else:
            # Fallback: calculer depuis l'image
            dpi = 400
            width_cm = round((image_size[0] / dpi) * 2.54, 1)
            height_cm = round((image_size[1] / dpi) * 2.54, 1)
    else:
        # Calculer les dimensions en cm (approximation basée sur DPI 400)
        dpi = 400
        width_cm = round((image_size[0] / dpi) * 2.54, 1)
        height_cm = round((image_size[1] / dpi) * 2.54, 1)
    
    # Créer la description avec les vraies informations
    description = f"{artist_name}, {title}. Medium: {details['medium']}. Size: {width_cm} x {height_cm} cm. Execution year: {details['execution_year']}."
    
    artwork_json = {
        "artist_name": artist_name,
        "title": title,
        "id": artwork_id,
        "image_url": str(image_path),  # Chemin local vers l'image
        "size": [width_cm, height_cm],
        "size_unit": "cm",
        "medium": details["medium"],
        "signature": "No comment",
        "execution_year": details["execution_year"],
        "description": description,
        "provenance": ["No comment"],
        "literature": ["No comment"],
        "exhibition": ["No comment"],
        "plate_number": plate_number,
        "source_page": plate_info.get('page'),
        "extraction_date": datetime.now().isoformat()
    }
    
    return artwork_json


def save_artwork_json(artwork_data: Dict, output_dir: Path, plate_number: int) -> Path:
    """
    Sauvegarde le JSON d'une œuvre.
    
    Args:
        artwork_data: Données de l'œuvre
        output_dir: Dossier de sortie
        plate_number: Numéro de la planche
        
    Returns:
        Chemin vers le fichier JSON créé
    """
    json_filename = f"oeuvre_{plate_number:03d}.json"
    json_path = output_dir / json_filename
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(artwork_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"💾 JSON œuvre sauvegardé: {json_path}")
        return json_path
        
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde JSON œuvre: {e}")
        return None


def extract_artist_name_from_pdf(pdf_path: str) -> str:
    """
    Extrait le nom de l'artiste depuis le nom du fichier PDF.
    
    Args:
        pdf_path: Chemin vers le PDF
        
    Returns:
        Nom de l'artiste nettoyé
    """
    pdf_name = Path(pdf_path).stem
    
    # Nettoyer le nom (enlever extensions, numéros, etc.)
    # Exemple: "PABLO-PICASSO-VOL31-1969-multi-pagepdfocr_1" -> "PABLO PICASSO"
    
    # Enlever les parties communes
    clean_name = pdf_name
    clean_name = re.sub(r'-VOL\d+.*', '', clean_name)  # Enlever -VOL31-1969...
    clean_name = re.sub(r'-multi-page.*', '', clean_name)  # Enlever -multi-page...
    clean_name = re.sub(r'pdfocr.*', '', clean_name)  # Enlever pdfocr...
    clean_name = re.sub(r'_\d+$', '', clean_name)  # Enlever _1, _2...
    
    # Remplacer les tirets par des espaces
    clean_name = clean_name.replace('-', ' ')
    
    # Capitaliser chaque mot
    clean_name = ' '.join(word.capitalize() for word in clean_name.split())
    
    return clean_name if clean_name else "Artiste Inconnu"


def create_artwork_jsons_for_images(output_dir: Path, plate_map: Dict[int, Dict], 
                                  artist_name: str) -> Dict[str, int]:
    """
    Crée les JSONs d'œuvres pour toutes les images extraites.
    
    Args:
        output_dir: Dossier contenant les images extraites
        plate_map: Mapping des numéros de planches vers les infos
        artist_name: Nom de l'artiste
        
    Returns:
        Statistiques de création des JSONs
    """
    stats = {
        'total_images': 0,
        'jsons_created': 0,
        'skipped': 0,
        'not_matched': 0
    }
    
    logger.info("🎨 Création des JSONs d'œuvres...")
    
    # Parcourir toutes les images extraites
    for page_dir in output_dir.glob("page_*"):
        if not page_dir.is_dir():
            continue
            
        for image_file in page_dir.glob("*.png"):
            if image_file.name.startswith("thumb_"):
                continue
                
            stats['total_images'] += 1
            
            # Extraire le numéro de planche depuis le nom de fichier
            plate_number = _extract_number_from_filename(image_file.name)
            if plate_number is None:
                logger.warning(f"⚠️ Impossible d'extraire le numéro de {image_file.name}")
                stats['not_matched'] += 1
                continue
            
            # Vérifier si on a les infos du sommaire
            if plate_number not in plate_map:
                logger.warning(f"⚠️ Planche {plate_number} non trouvée dans le sommaire")
                stats['not_matched'] += 1
                continue
            
            try:
                # Obtenir les dimensions de l'image
                import cv2
                img = cv2.imread(str(image_file))
                if img is None:
                    logger.warning(f"⚠️ Impossible de lire l'image {image_file}")
                    stats['skipped'] += 1
                    continue
                
                image_size = (img.shape[1], img.shape[0])  # (width, height)
                
                # Créer le JSON de l'œuvre
                plate_info = plate_map[plate_number]
                artwork_data = create_artwork_json(
                    image_file, plate_number, plate_info, artist_name, image_size
                )
                
                # Sauvegarder le JSON
                json_path = save_artwork_json(artwork_data, page_dir, plate_number)
                if json_path:
                    stats['jsons_created'] += 1
                    logger.debug(f"✅ JSON créé pour œuvre {plate_number}: {json_path}")
                
            except Exception as e:
                logger.error(f"❌ Erreur création JSON pour {image_file}: {e}")
                stats['skipped'] += 1
    
    return stats


def prompt_for_renaming() -> bool:
    """Prompt user for renaming confirmation"""
    try:
        ans = input("🔄 Renommer les images selon le sommaire ? [o/N]: ").strip().lower()
        return ans in ("o", "oui", "y", "yes")
    except (KeyboardInterrupt, EOFError):
        print("\n❌ Annulé par l'utilisateur")
        return False
