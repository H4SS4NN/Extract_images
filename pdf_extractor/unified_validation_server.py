#!/usr/bin/env python3
"""
Serveur Flask UNIFIÉ pour l'interface de validation des extractions PDF ULTRA
Gère à la fois Picasso et Dubuffet avec OCR sur un seul port
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permettre les requêtes cross-origin

# Configuration
EXTRACTIONS_DIR = "extractions_ultra"
UPLOAD_DIR = "uploads"

class UnifiedValidationServer:
    def __init__(self):
        self.current_session = None
        self.sessions = self.scan_sessions()
    
    def scan_sessions(self):
        """Scanner TOUTES les sessions d'extraction disponibles (Picasso + Dubuffet)"""
        sessions = []
        
        if not os.path.exists(EXTRACTIONS_DIR):
            return sessions
        
        for session_dir in os.listdir(EXTRACTIONS_DIR):
            session_path = os.path.join(EXTRACTIONS_DIR, session_dir)
            
            if os.path.isdir(session_path):
                # Détecter le type de collection
                is_dubuffet = "DUBUFFET" in session_dir.upper()
                is_picasso = "PICASSO" in session_dir.upper() or not is_dubuffet  # Par défaut Picasso
                
                # Lire les métadonnées de la session
                meta_file = os.path.join(session_path, "extraction_ultra_complete.json")
                
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        # Vérifier les résultats OCR Dubuffet
                        ocr_results = None
                        individual_jsons = 0
                        if is_dubuffet:
                            dubuffet_ocr_file = os.path.join(session_path, "dubuffet_ocr_results.json")
                            if os.path.exists(dubuffet_ocr_file):
                                try:
                                    with open(dubuffet_ocr_file, 'r', encoding='utf-8') as f:
                                        ocr_results = json.load(f)
                                except:
                                    pass
                            
                            # Compter les JSON d'œuvres individuelles
                            individual_jsons = len(list(Path(session_path).rglob("oeuvre_*.json")))
                        
                        session_data = {
                            'name': session_dir,
                            'path': session_path,
                            'pdf_name': meta.get('pdf_name', 'Inconnu'),
                            'total_pages': int(meta.get('total_pages', 0) or 0),
                            'total_images': int(meta.get('total_images_extracted', 0) or 0),
                            'start_time': meta.get('start_time', ''),
                            'mode': meta.get('mode', 'ULTRA_SENSIBLE'),
                            'collection_type': 'dubuffet' if is_dubuffet else 'picasso',
                            'is_dubuffet': is_dubuffet,
                            'is_picasso': is_picasso,
                            'has_ocr': ocr_results is not None,
                            'ocr_artworks': len(ocr_results.get('artworks', {})) if ocr_results else 0,
                            'individual_jsons': individual_jsons,
                            # CORRECTION DÉCALAGE : Stocker start_page
                            'start_page': meta.get('start_page', 1)
                        }
                        sessions.append(session_data)
                    except Exception as e:
                        print(f"Erreur lecture métadonnées {session_dir}: {e}")
        
        # Trier par date (plus récent en premier)
        try:
            sessions.sort(key=lambda x: x.get('start_time') or '', reverse=True)
        except Exception:
            pass
        
        return sessions
    
    def get_page_images_with_ocr(self, session_name, page_num):
        """Récupérer toutes les images d'une page avec données OCR (Dubuffet) ou classiques (Picasso)"""
        session_path = os.path.join(EXTRACTIONS_DIR, session_name)
        
        # CORRECTION DÉCALAGE : Convertir page_num (1-based) vers page réelle
        session = next((s for s in self.sessions if s['name'] == session_name), None)
        start_page = session.get('start_page', 1) if session else 1
        actual_page_num = start_page + page_num - 1
        
        page_dir = os.path.join(session_path, f"page_{actual_page_num:03d}")
        
        if not os.path.exists(page_dir):
            return [], {}
        
        # Trouver la session pour connaître le type
        session = next((s for s in self.sessions if s['name'] == session_name), None)
        is_dubuffet = session and session.get('is_dubuffet', False)
        
        images = []
        
        # Lire les détails de la page si disponibles
        page_details_file = os.path.join(page_dir, "page_ultra_details.json")
        page_details = {}
        if os.path.exists(page_details_file):
            try:
                with open(page_details_file, 'r', encoding='utf-8') as f:
                    page_details = json.load(f)
            except:
                pass
        
        rectangles_details = page_details.get('rectangles_details', [])
        
        # Scanner les images normales
        for img_file in glob.glob(os.path.join(page_dir, "*.png")):
            if "thumb_" in os.path.basename(img_file) or "ocr_debug" in os.path.basename(img_file):
                continue  # Ignorer les miniatures et debug OCR
            
            filename = os.path.basename(img_file)
            
            # Trouver les détails correspondants
            details = next((r for r in rectangles_details if r.get('filename') == filename), {})
            
            # Base des informations
            image_info = {
                'filename': filename,
                'path': os.path.relpath(img_file, EXTRACTIONS_DIR),
                'is_doubtful': details.get('is_doubtful', False),
                'confidence': details.get('confidence', 1.0),
                'doubt_reasons': details.get('doubt_reasons', []),
                'was_rotated': details.get('was_rotated', False),
                'artwork_number': details.get('artwork_number'),
                'size_kb': details.get('size_kb', 0),
                'detection_method': details.get('detection_method', 'unknown'),
                'dimensions': f"{details.get('bbox', {}).get('w', 0)}×{details.get('bbox', {}).get('h', 0)}",
                'bbox': details.get('bbox', {}),
                'folder': 'normal'
            }
            
            # SPÉCIFIQUE DUBUFFET : Ajouter données OCR
            if is_dubuffet:
                # Chercher le JSON d'œuvre correspondant
                artwork_json_path = None
                artwork_data = None
                for json_file in glob.glob(os.path.join(page_dir, "oeuvre_*.json")):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                        if json_data.get('image_file') == filename:
                            artwork_json_path = json_file
                            artwork_data = json_data
                            break
                    except:
                        continue
                
                image_info.update({
                    'has_ocr': artwork_data is not None,
                    'ocr_title': artwork_data.get('title') if artwork_data else None,
                    'ocr_medium': artwork_data.get('medium') if artwork_data else None,
                    'ocr_dimensions': artwork_data.get('dimensions_cm') if artwork_data else None,
                    'ocr_date': artwork_data.get('date_text') if artwork_data else None,
                    'ocr_confidence': artwork_data.get('ocr_confidence') if artwork_data else None,
                    'ocr_region': artwork_data.get('ocr_region') if artwork_data else None,
                    'artwork_json': os.path.basename(artwork_json_path) if artwork_json_path else None
                })
            else:
                # PICASSO : Ajouter données du sommaire si disponibles
                toc_info = None
                if details.get('artwork_number'):
                    toc_info = self._get_toc_info_for_artwork(session_path, details.get('artwork_number'))
                
                image_info.update({
                    'has_ocr': False,
                    'ocr_title': None,
                    'ocr_medium': None,
                    'ocr_dimensions': None,
                    'ocr_date': None,
                    'ocr_confidence': None,
                    'ocr_region': None,
                    'artwork_json': None,
                    'toc_info': toc_info  # Informations du sommaire
                })
            
            images.append(image_info)
        
        # Scanner le dossier DOUTEUX
        doubtful_dir = os.path.join(page_dir, "DOUTEUX")
        if os.path.exists(doubtful_dir):
            for img_file in glob.glob(os.path.join(doubtful_dir, "DOUTEUX_*.png")):
                filename = os.path.basename(img_file)
                base_filename = filename.replace("DOUTEUX_", "")
                
                # Chercher le fichier info correspondant
                info_file = os.path.join(doubtful_dir, base_filename.replace('.png', '_INFO.txt'))
                doubt_info = ""
                if os.path.exists(info_file):
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f:
                            doubt_info = f.read()
                    except:
                        pass
                
                # Trouver les détails correspondants
                details = next((r for r in rectangles_details if r.get('filename') == filename), {})
                
                # Pour les images douteuses, ajouter aussi les infos du sommaire si Picasso
                toc_info_doubtful = None
                if not is_dubuffet and details.get('artwork_number'):
                    toc_info_doubtful = self._get_toc_info_for_artwork(session_path, details.get('artwork_number'))
                
                images.append({
                    'filename': filename,
                    'path': os.path.relpath(img_file, EXTRACTIONS_DIR),
                    'is_doubtful': True,
                    'confidence': details.get('confidence', 0.5),
                    'doubt_reasons': details.get('doubt_reasons', []),
                    'doubt_info': doubt_info,
                    'was_rotated': details.get('was_rotated', False),
                    'artwork_number': details.get('artwork_number'),
                    'size_kb': details.get('size_kb', 0),
                    'detection_method': details.get('detection_method', 'unknown'),
                    'dimensions': f"{details.get('bbox', {}).get('w', 0)}×{details.get('bbox', {}).get('h', 0)}",
                    'bbox': details.get('bbox', {}),
                    'folder': 'DOUTEUX',
                    'has_ocr': False,
                    'toc_info': toc_info_doubtful  # Informations du sommaire pour Picasso
                })
        
        # Trier par nom de fichier
        images.sort(key=lambda x: x['filename'])
        
        # Métadonnées de page
        page_meta = {
            'page_width': 0,
            'page_height': 0,
            'page_dpi': 0,
            'collection_type': session.get('collection_type', 'picasso') if session else 'picasso'
        }
        
        # SPÉCIFIQUE DUBUFFET : Images debug OCR
        if is_dubuffet:
            ocr_debug_images = []
            for debug_file in glob.glob(os.path.join(page_dir, "ocr_debug_*.png")):
                debug_filename = os.path.basename(debug_file)
                
                # Chercher le fichier texte correspondant
                txt_file = debug_file.replace('.png', '.txt')
                ocr_text = ""
                if os.path.exists(txt_file):
                    try:
                        with open(txt_file, 'r', encoding='utf-8') as f:
                            ocr_text = f.read()
                    except:
                        pass
                
                ocr_debug_images.append({
                    'filename': debug_filename,
                    'path': os.path.relpath(debug_file, EXTRACTIONS_DIR),
                    'ocr_text': ocr_text,
                    'is_debug': True
                })
            
            page_meta.update({
                'ocr_debug_count': len(ocr_debug_images),
                'ocr_debug_images': ocr_debug_images
            })
        else:
            page_meta.update({
                'ocr_debug_count': 0,
                'ocr_debug_images': []
            })
        
        # Extraire meta de taille
        size_str = page_details.get('image_size') or ''
        if isinstance(size_str, str) and '×' in size_str:
            try:
                w_str, h_str = size_str.split('×')
                page_meta['page_width'] = int(w_str)
                page_meta['page_height'] = int(h_str)
            except Exception:
                pass
        page_meta['page_dpi'] = int(page_details.get('dpi_used') or 0)
        
        return images, page_meta
    
    def _get_toc_info_for_artwork(self, session_path, artwork_number):
        """Récupérer les informations du sommaire pour un numéro d'œuvre donné"""
        if not artwork_number:
            return None
            
        # Convertir en entier si c'est une string
        try:
            artwork_num = int(artwork_number)
        except (ValueError, TypeError):
            return None
            
        # Chercher le fichier sommaire_planches.json
        toc_file = os.path.join(session_path, "sommaire_planches.json")
        if not os.path.exists(toc_file):
            return None
            
        try:
            with open(toc_file, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
            
            # Chercher l'œuvre avec le bon numéro
            plates = toc_data.get('plates', [])
            for plate in plates:
                if plate.get('number') == artwork_num:
                    return {
                        'number': plate.get('number'),
                        'title': plate.get('title'),
                        'page': plate.get('page'),
                        'raw_line': plate.get('raw_line'),
                        'pattern_used': plate.get('pattern_used')
                    }
                    
        except Exception as e:
            print(f"Erreur lecture sommaire: {e}")
            
        return None
    
    def _update_image_crop_metadata(self, session_path, image_path, crop_metadata):
        """Mettre à jour les métadonnées de crop d'une image"""
        try:
            # Extraire les informations du chemin
            path_parts = image_path.replace('\\', '/').split('/')
            page_dir = None
            filename = None
            
            for i, part in enumerate(path_parts):
                if part.startswith('page_'):
                    page_dir = part
                    if i + 1 < len(path_parts):
                        remaining_parts = path_parts[i+1:]
                        if 'DOUTEUX' in remaining_parts:
                            filename = remaining_parts[-1]  # Dernier élément
                        else:
                            filename = remaining_parts[0] if remaining_parts else None
                    break
            
            if not page_dir or not filename:
                print(f"Impossible d'extraire page_dir et filename de: {image_path}")
                return False
            
            # Charger les détails de la page
            page_details_file = os.path.join(session_path, page_dir, "page_ultra_details.json")
            
            if os.path.exists(page_details_file):
                with open(page_details_file, 'r', encoding='utf-8') as f:
                    page_details = json.load(f)
                
                # Trouver et mettre à jour les détails du rectangle correspondant
                rectangles_details = page_details.get('rectangles_details', [])
                
                for rect in rectangles_details:
                    if rect.get('filename') == filename or rect.get('filename') == filename.replace('DOUTEUX_', ''):
                        # Ajouter les métadonnées de crop
                        rect['crop_metadata'] = crop_metadata
                        rect['was_cropped'] = True
                        rect['crop_timestamp'] = datetime.now().isoformat()
                        break
                
                # Sauvegarder les détails mis à jour
                with open(page_details_file, 'w', encoding='utf-8') as f:
                    json.dump(page_details, f, indent=2, ensure_ascii=False)
                
                print(f"📝 Métadonnées de crop mises à jour pour {filename}")
                return True
            else:
                print(f"❌ Fichier page_ultra_details.json non trouvé: {page_details_file}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur mise à jour métadonnées crop: {e}")
            return False
    
    def apply_crop_to_image(self, session_path, image_path, crop_data):
        """Appliquer un crop à une image"""
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import shutil
            import re
            
            print(f"🔧 Crop data received: {crop_data}")
            
            # Chemins des fichiers
            full_image_path = os.path.join(EXTRACTIONS_DIR, image_path)
            
            if not os.path.exists(full_image_path):
                print(f"❌ Image non trouvée: {full_image_path}")
                return False
            
            # Charger l'image avec OpenCV
            image = cv2.imread(full_image_path)
            if image is None:
                print(f"❌ Impossible de charger l'image: {full_image_path}")
                return False
            
            # Calculer les coordonnées réelles du crop
            img_height, img_width = image.shape[:2]
            print(f"📏 Image originale: {img_width}x{img_height}")
            
            # Coordonnées du crop (normalisées par rapport à l'image affichée)
            display_width = crop_data.get('displayWidth', img_width)
            display_height = crop_data.get('displayHeight', img_height)
            
            # Facteurs de mise à l'échelle
            scale_x = img_width / display_width
            scale_y = img_height / display_height
            
            print(f"🔄 Facteurs d'échelle: x={scale_x:.2f}, y={scale_y:.2f}")
            
            # Coordonnées réelles du crop
            x = int(crop_data['x'] * scale_x)
            y = int(crop_data['y'] * scale_y)
            w = int(crop_data['width'] * scale_x)
            h = int(crop_data['height'] * scale_y)
            
            # Valider les coordonnées
            x = max(0, min(x, img_width - 1))
            y = max(0, min(y, img_height - 1))
            w = max(1, min(w, img_width - x))
            h = max(1, min(h, img_height - y))
            
            print(f"✂️ Crop coords: x={x}, y={y}, w={w}, h={h}")
            
            # Effectuer le crop
            cropped_image = image[y:y+h, x:x+w]
            
            # Sauvegarder l'image originale si ce n'est pas déjà fait
            backup_path = full_image_path + '.backup'
            if not os.path.exists(backup_path):
                shutil.copy2(full_image_path, backup_path)
                print(f"💾 Backup créé: {backup_path}")
            
            # Sauvegarder l'image croppée
            success = cv2.imwrite(full_image_path, cropped_image)
            
            if success:
                print(f"✅ Image croppée sauvegardée: {full_image_path}")
                
                # Mettre à jour les métadonnées de l'image
                self._update_image_crop_metadata(session_path, image_path, {
                    'original_size': (img_width, img_height),
                    'crop_coords': (x, y, w, h),
                    'cropped_size': (w, h),
                    'crop_applied': True,
                    'crop_timestamp': datetime.now().isoformat()
                })
                
                return True
            else:
                print("❌ Erreur lors de la sauvegarde de l'image croppée")
                return False
                
        except Exception as e:
            print(f"❌ Erreur crop: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_dubuffet_artwork(self, session_path, image_path, artwork_number, title, artist, 
                               medium, date, width, height, confidence, detection_method, is_doubtful):
        """Mettre à jour les métadonnées d'une œuvre Dubuffet"""
        try:
            print(f"🎨 Updating Dubuffet artwork: {title} by {artist}")
            
            # Extraire le nom de fichier depuis le chemin
            filename = os.path.basename(image_path)
            if filename.startswith('DOUTEUX_'):
                filename = filename.replace('DOUTEUX_', '')
            
            # Trouver la page et le dossier
            path_parts = image_path.replace('\\', '/').split('/')
            page_dir = None
            for part in path_parts:
                if part.startswith('page_'):
                    page_dir = part
                    break
            
            if not page_dir:
                print(f"❌ Impossible de trouver le dossier de page dans: {image_path}")
                return False
            
            page_folder = os.path.join(session_path, page_dir)
            
            # Chercher le fichier JSON d'œuvre correspondant
            artwork_json_path = None
            for json_file in glob.glob(os.path.join(page_folder, "oeuvre_*.json")):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    if json_data.get('image_file') == filename:
                        artwork_json_path = json_file
                        break
                except:
                    continue
            
            if artwork_json_path:
                # Mettre à jour le JSON existant
                with open(artwork_json_path, 'r', encoding='utf-8') as f:
                    artwork_data = json.load(f)
                
                # Mettre à jour les champs
                artwork_data['title'] = title
                artwork_data['medium'] = medium
                artwork_data['date_text'] = date
                artwork_data['plate_number'] = artwork_number
                
                if width and height:
                    artwork_data['dimensions_cm'] = {
                        'width': float(width) if width else None,
                        'height': float(height) if height else None
                    }
                
                artwork_data['confidence'] = confidence
                artwork_data['detection_method'] = detection_method
                artwork_data['is_doubtful'] = is_doubtful
                artwork_data['last_modified'] = datetime.now().isoformat()
                
                # Sauvegarder
                with open(artwork_json_path, 'w', encoding='utf-8') as f:
                    json.dump(artwork_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅ JSON Dubuffet mis à jour: {artwork_json_path}")
            else:
                # Créer un nouveau JSON si pas trouvé
                artwork_data = {
                    'image_file': filename,
                    'title': title,
                    'medium': medium,
                    'date_text': date,
                    'plate_number': artwork_number,
                    'dimensions_cm': {
                        'width': float(width) if width else None,
                        'height': float(height) if height else None
                    } if width and height else None,
                    'confidence': confidence,
                    'detection_method': detection_method,
                    'is_doubtful': is_doubtful,
                    'created_by': 'manual_edit',
                    'created_at': datetime.now().isoformat(),
                    'last_modified': datetime.now().isoformat()
                }
                
                # Générer un nom de fichier JSON unique
                json_filename = f"oeuvre_{artwork_number or 'manual'}_{datetime.now().strftime('%H%M%S')}.json"
                new_json_path = os.path.join(page_folder, json_filename)
                
                with open(new_json_path, 'w', encoding='utf-8') as f:
                    json.dump(artwork_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅ Nouveau JSON Dubuffet créé: {new_json_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur mise à jour Dubuffet: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_picasso_artwork(self, session_path, image_path, artwork_number, title, artist,
                              catalog_page, raw_line, confidence, detection_method, is_doubtful):
        """Mettre à jour les métadonnées d'une œuvre Picasso"""
        try:
            print(f"🎭 Updating Picasso artwork: {title} by {artist}")
            
            # 1. Mettre à jour les détails de la page
            success_page_details = self._update_picasso_page_details(
                session_path, image_path, artwork_number, title, confidence, detection_method, is_doubtful
            )
            
            # 2. Mettre à jour le sommaire si nécessaire
            success_toc = True
            if artwork_number and (title or raw_line):
                success_toc = self._update_picasso_toc(
                    session_path, artwork_number, title, catalog_page, raw_line
                )
            
            return success_page_details and success_toc
            
        except Exception as e:
            print(f"❌ Erreur mise à jour Picasso: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _update_picasso_page_details(self, session_path, image_path, artwork_number, title, confidence, detection_method, is_doubtful):
        """Mettre à jour les détails de page pour Picasso"""
        try:
            # Extraire les informations du chemin
            path_parts = image_path.replace('\\', '/').split('/')
            page_dir = None
            filename = None
            
            for i, part in enumerate(path_parts):
                if part.startswith('page_'):
                    page_dir = part
                    if i + 1 < len(path_parts):
                        remaining_parts = path_parts[i+1:]
                        if 'DOUTEUX' in remaining_parts:
                            filename = remaining_parts[-1]
                        else:
                            filename = remaining_parts[0] if remaining_parts else None
                    break
            
            if not page_dir or not filename:
                print(f"❌ Impossible d'extraire page_dir et filename de: {image_path}")
                return False
            
            # Charger les détails de la page
            page_details_file = os.path.join(session_path, page_dir, "page_ultra_details.json")
            
            if os.path.exists(page_details_file):
                with open(page_details_file, 'r', encoding='utf-8') as f:
                    page_details = json.load(f)
                
                # Trouver et mettre à jour les détails du rectangle correspondant
                rectangles_details = page_details.get('rectangles_details', [])
                
                for rect in rectangles_details:
                    if rect.get('filename') == filename or rect.get('filename') == filename.replace('DOUTEUX_', ''):
                        # Mettre à jour les champs
                        rect['artwork_number'] = artwork_number
                        rect['title'] = title
                        rect['confidence'] = confidence
                        rect['detection_method'] = detection_method
                        rect['is_doubtful'] = is_doubtful
                        rect['last_modified'] = datetime.now().isoformat()
                        rect['modified_by'] = 'manual_edit'
                        break
                
                # Sauvegarder les détails mis à jour
                with open(page_details_file, 'w', encoding='utf-8') as f:
                    json.dump(page_details, f, indent=2, ensure_ascii=False)
                
                print(f"✅ Détails de page Picasso mis à jour pour {filename}")
                return True
            else:
                print(f"❌ Fichier page_ultra_details.json non trouvé: {page_details_file}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur mise à jour détails page Picasso: {e}")
            return False
    
    def _update_picasso_toc(self, session_path, artwork_number, title, catalog_page, raw_line):
        """Mettre à jour le sommaire Picasso"""
        try:
            if not artwork_number:
                return True  # Rien à faire
            
            artwork_num = int(artwork_number)
            toc_file = os.path.join(session_path, "sommaire_planches.json")
            
            if not os.path.exists(toc_file):
                print(f"❌ Fichier sommaire non trouvé: {toc_file}")
                return False
            
            # Charger le sommaire
            with open(toc_file, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
            
            # Chercher et mettre à jour l'entrée
            plates = toc_data.get('plates', [])
            found = False
            
            for plate in plates:
                if plate.get('number') == artwork_num:
                    # Mettre à jour les champs
                    if title:
                        plate['title'] = title
                    if catalog_page:
                        plate['page'] = catalog_page
                    if raw_line:
                        plate['raw_line'] = raw_line
                    plate['last_modified'] = datetime.now().isoformat()
                    plate['modified_by'] = 'manual_edit'
                    found = True
                    break
            
            if not found and title:
                # Créer une nouvelle entrée
                new_plate = {
                    'number': artwork_num,
                    'title': title,
                    'page': catalog_page,
                    'raw_line': raw_line or f"{artwork_num} {title}",
                    'pattern_used': 'manual_edit',
                    'created_by': 'manual_edit',
                    'created_at': datetime.now().isoformat(),
                    'last_modified': datetime.now().isoformat()
                }
                plates.append(new_plate)
                # Trier par numéro
                plates.sort(key=lambda x: x.get('number', 0))
                print(f"✅ Nouvelle entrée sommaire créée pour l'œuvre #{artwork_num}")
            
            # Sauvegarder le sommaire mis à jour
            with open(toc_file, 'w', encoding='utf-8') as f:
                json.dump(toc_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Sommaire Picasso mis à jour pour l'œuvre #{artwork_num}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur mise à jour sommaire Picasso: {e}")
            return False
    
    def save_validation_state(self, session_path, image_id, validation_state):
        """Sauvegarder l'état de validation d'une image"""
        try:
            # Fichier pour stocker les états de validation
            validation_file = os.path.join(session_path, "validation_states.json")
            
            # Charger les états existants
            validation_states = {}
            if os.path.exists(validation_file):
                try:
                    with open(validation_file, 'r', encoding='utf-8') as f:
                        validation_states = json.load(f)
                except:
                    validation_states = {}
            
            # Mettre à jour l'état
            validation_states[image_id] = {
                'state': validation_state,
                'timestamp': datetime.now().isoformat(),
                'validated_by': 'manual_validation'
            }
            
            # Sauvegarder
            with open(validation_file, 'w', encoding='utf-8') as f:
                json.dump(validation_states, f, indent=2, ensure_ascii=False)
            
            print(f"✅ État de validation sauvegardé: {image_id} = {validation_state}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde état validation: {e}")
            return False

# Instance globale du serveur
validation_server = UnifiedValidationServer()

@app.route('/')
def index():
    """Page principale - Interface unifiée professionnelle"""
    return send_file('professional_validation_interface.html')

@app.route('/api/sessions')
def get_sessions():
    """Récupérer TOUTES les sessions disponibles (Picasso + Dubuffet)"""
    # Re-scan automatique à chaque appel
    try:
        validation_server.sessions = validation_server.scan_sessions()
    except Exception:
        pass
    
    return jsonify({
        'sessions': validation_server.sessions,
        'current_session': validation_server.current_session
    })

@app.route('/api/session/<session_name>')
def set_session(session_name):
    """Définir la session active"""
    session = next((s for s in validation_server.sessions if s['name'] == session_name), None)
    if not session:
        return jsonify({'error': 'Session non trouvée'}), 404
    
    validation_server.current_session = session
    return jsonify({'success': True, 'session': session})

@app.route('/api/get-session-data')
def get_session_data():
    """Récupérer les données de la session active"""
    # Assurer un rescAN pour capter la dernière session
    validation_server.sessions = validation_server.scan_sessions()
    
    if not validation_server.current_session:
        # Utiliser la première session disponible
        if validation_server.sessions:
            validation_server.current_session = validation_server.sessions[0]
        else:
            return jsonify({'error': 'Aucune session disponible'}), 404
    
    session = validation_server.current_session
    return jsonify({
        'sessionName': session['name'],
        'pdfName': session['pdf_name'],
        'totalPages': session['total_pages'],
        'totalImages': session['total_images'],
        'mode': session['mode'],
        'startTime': session['start_time'],
        'path': session['path'],
        'collectionType': session.get('collection_type', 'picasso'),
        'isDubuffet': session.get('is_dubuffet', False),
        'isPicasso': session.get('is_picasso', True),
        'hasOCR': session.get('has_ocr', False),
        'ocrArtworks': session.get('ocr_artworks', 0),
        'individualJsons': session.get('individual_jsons', 0),
        'startPage': session.get('start_page', 1)  # CORRECTION DÉCALAGE
    })

@app.route('/api/get-page-images/<int:page_num>')
def get_page_images(page_num):
    """Récupérer les images d'une page spécifique avec données OCR si Dubuffet"""
    if not validation_server.current_session:
        validation_server.sessions = validation_server.scan_sessions()
        if validation_server.sessions:
            validation_server.current_session = validation_server.sessions[0]
        else:
            return jsonify({'error': 'Aucune session active'}), 400
    
    session_name = validation_server.current_session['name']
    images, page_meta = validation_server.get_page_images_with_ocr(session_name, page_num)
    
    return jsonify({
        'page': page_num,
        'session': session_name,
        'images': images,
        'count': len(images),
        'meta': page_meta,
        'collectionType': validation_server.current_session.get('collection_type', 'picasso'),
        'isDubuffet': validation_server.current_session.get('is_dubuffet', False)
    })

@app.route('/api/get-image/<path:image_path>')
def get_image(image_path):
    """Servir une image spécifique"""
    try:
        # Construire le chemin complet
        full_path = os.path.join(EXTRACTIONS_DIR, image_path)
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'Image non trouvée'}), 404
        
        # Servir le fichier
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        return send_from_directory(directory, filename)
    
    except Exception as e:
        return jsonify({'error': f'Erreur servir image: {str(e)}'}), 500

@app.route('/api/get-artwork-json/<int:page_num>/<artwork_filename>')
def get_artwork_json(page_num, artwork_filename):
    """Récupérer le JSON d'une œuvre spécifique (Dubuffet uniquement)"""
    if not validation_server.current_session:
        return jsonify({'error': 'Aucune session active'}), 400
    
    if not validation_server.current_session.get('is_dubuffet', False):
        return jsonify({'error': 'Fonctionnalité disponible uniquement pour Dubuffet'}), 400
    
    session_path = validation_server.current_session['path']
    page_dir = os.path.join(session_path, f"page_{page_num:03d}")
    
    # Chercher le JSON correspondant
    for json_file in glob.glob(os.path.join(page_dir, "oeuvre_*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            if json_data.get('image_file') == artwork_filename:
                return jsonify(json_data)
        except:
            continue
    
    return jsonify({'error': 'JSON d\'œuvre non trouvé'}), 404

@app.route('/api/get-pdf-page/<int:page_num>')
def get_pdf_page(page_num):
    """Récupérer l'image de la page PDF originale avec CORRECTION DÉCALAGE"""
    if not validation_server.current_session:
        return jsonify({'error': 'Aucune session active'}), 400
    
    # Lire les métadonnées pour trouver le PDF original
    session_path = validation_server.current_session['path']
    meta_file = os.path.join(session_path, "extraction_ultra_complete.json")
    
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            pdf_path = meta.get('pdf_original_path') or meta.get('pdf_path')
            
            if pdf_path and os.path.exists(pdf_path):
                # Convertir la page PDF en image
                try:
                    from pdf2image import convert_from_path
                    
                    # CORRECTION DÉCALAGE : Utiliser start_page de la session
                    start_page = validation_server.current_session.get('start_page', 1)
                    pdf_page_num = start_page + page_num - 1
                    
                    
                    page_images = convert_from_path(
                        pdf_path, 
                        dpi=200,  # DPI raisonnable pour l'affichage web
                        first_page=pdf_page_num,
                        last_page=pdf_page_num
                    )
                    
                    if page_images:
                        # Sauvegarder temporairement l'image
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            page_images[0].save(tmp.name, 'PNG')
                            
                            # Servir l'image temporaire
                            return send_file(tmp.name, mimetype='image/png')
                    
                except Exception as e:
                    return jsonify({
                        'error': f'Erreur conversion PDF: {str(e)}',
                        'pdf_path': pdf_path,
                        'debug_info': f'page_num={page_num}, start_page={start_page}, pdf_page_num={pdf_page_num}'
                    }), 500
            else:
                return jsonify({
                    'error': 'PDF original non trouvé',
                    'pdf_path': pdf_path,
                    'exists': os.path.exists(pdf_path) if pdf_path else False
                }), 404
                
        except Exception as e:
            return jsonify({'error': f'Erreur métadonnées: {str(e)}'}), 500
    
    # Fallback sur placeholder
    return jsonify({
        'page': page_num,
        'image_url': f'/api/placeholder-pdf/{page_num}',
        'message': 'Métadonnées non trouvées - mode placeholder'
    })

@app.route('/api/placeholder-pdf/<int:page_num>')
def placeholder_pdf(page_num):
    """Image placeholder pour la page PDF"""
    # Créer une image SVG simple comme placeholder
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 400 600">
        <rect width="400" height="600" fill="#f0f0f0"/>
        <text x="200" y="300" font-family="Arial" font-size="24" fill="#666" text-anchor="middle">PDF Page {page_num}</text>
        <text x="200" y="350" font-family="Arial" font-size="14" fill="#999" text-anchor="middle">Session: {validation_server.current_session['name'] if validation_server.current_session else 'None'}</text>
    </svg>'''
    
    return svg_content, 200, {'Content-Type': 'image/svg+xml'}

@app.route('/api/save-validation', methods=['POST'])
def save_validation():
    """Sauvegarder les résultats de validation (Picasso + Dubuffet)"""
    try:
        data = request.get_json()
        
        if not validation_server.current_session:
            return jsonify({'error': 'Aucune session active'}), 400
        
        # Créer le fichier de résultats
        session_path = validation_server.current_session['path']
        collection_type = validation_server.current_session.get('collection_type', 'picasso')
        results_file = os.path.join(session_path, f"{collection_type}_validation_results.json")
        
        # Ajouter des métadonnées
        validation_data = {
            'session_name': data.get('sessionName'),
            'validation_timestamp': datetime.now().isoformat(),
            'total_pages': data.get('totalPages'),
            'image_states': data.get('imageStates', {}),
            'ocr_validations': data.get('ocrValidations', {}),
            'summary': data.get('summary', {}),
            'validator_info': {
                'version': '3.0',
                'interface': 'Unified Validation Interface',
                'collection': collection_type.title()
            }
        }
        
        # Sauvegarder
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': f'Validation {collection_type.title()} sauvegardée avec succès',
            'file': results_file
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur sauvegarde: {str(e)}'
        }), 500

@app.route('/api/export-validated-images', methods=['POST'])
def export_validated_images():
    """Exporter uniquement les images validées"""
    try:
        data = request.get_json()
        image_states = data.get('imageStates', {})
        
        if not validation_server.current_session:
            return jsonify({'error': 'Aucune session active'}), 400
        
        # Créer un dossier d'export
        session_path = validation_server.current_session['path']
        collection_type = validation_server.current_session.get('collection_type', 'picasso')
        export_dir = os.path.join(session_path, f"VALIDATED_IMAGES_{collection_type.upper()}")
        os.makedirs(export_dir, exist_ok=True)
        
        validated_count = 0
        
        # Copier les images validées
        for image_id, state in image_states.items():
            if state == 'validated':
                # Extraire les infos de l'image_id (format: pageX_imgY ou pageX_filename)
                parts = image_id.split('_', 1)
                if len(parts) >= 2:
                    page_part = parts[0]
                    filename_part = parts[1]
                    
                    # Extraire le numéro de page
                    page_num = int(page_part.replace('page', ''))
                    
                    # Chercher l'image dans le dossier de la page
                    page_dir = os.path.join(session_path, f"page_{page_num:03d}")
                    
                    # Chercher dans le dossier normal
                    img_path = os.path.join(page_dir, filename_part)
                    if not os.path.exists(img_path):
                        # Chercher dans le dossier DOUTEUX
                        img_path = os.path.join(page_dir, "DOUTEUX", filename_part)
                    
                    if os.path.exists(img_path):
                        # Copier l'image
                        import shutil
                        dest_path = os.path.join(export_dir, f"page{page_num:03d}_{filename_part}")
                        shutil.copy2(img_path, dest_path)
                        validated_count += 1
        
        return jsonify({
            'success': True,
            'message': f'{validated_count} images {collection_type} validées exportées',
            'export_dir': export_dir,
            'count': validated_count
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur export: {str(e)}'
        }), 500

@app.route('/api/save-artwork-changes', methods=['POST'])
def save_artwork_changes():
    """Sauvegarder les modifications d'une œuvre"""
    try:
        data = request.get_json()
        
        # Extraire les données
        image_id = data.get('imageId')
        image_path = data.get('imagePath')
        crop_data = data.get('cropData')
        
        # Informations de base
        artwork_number = data.get('artworkNumber')
        title = data.get('title')
        artist = data.get('artist')
        confidence = data.get('confidence')
        detection_method = data.get('detectionMethod')
        is_doubtful = data.get('isDoubtful')
        validation_state = data.get('validationState')  # Nouvel état de validation
        
        if not validation_server.current_session:
            return jsonify({'success': False, 'error': 'Aucune session active'}), 400
        
        session_name = validation_server.current_session['name']
        session_path = os.path.join(EXTRACTIONS_DIR, session_name)
        
        # Traitement du crop si fourni
        if crop_data:
            success = validation_server.apply_crop_to_image(session_path, image_path, crop_data)
            if not success:
                return jsonify({'success': False, 'error': 'Failed to apply crop'}), 500
        
        # Mise à jour des métadonnées
        if validation_server.current_session.get('is_dubuffet'):
            # Traitement spécifique Dubuffet
            medium = data.get('medium')
            date = data.get('date')
            width = data.get('width')
            height = data.get('height')
            
            success = validation_server.update_dubuffet_artwork(
                session_path, image_path, artwork_number, title, artist,
                medium, date, width, height, confidence, detection_method, is_doubtful
            )
        else:
            # Traitement spécifique Picasso
            catalog_page = data.get('catalogPage')
            raw_line = data.get('rawLine')
            
            success = validation_server.update_picasso_artwork(
                session_path, image_path, artwork_number, title, artist,
                catalog_page, raw_line, confidence, detection_method, is_doubtful
            )
        
        # Sauvegarder l'état de validation si fourni
        if validation_state:
            validation_success = validation_server.save_validation_state(
                session_path, image_id, validation_state
            )
            if not validation_success:
                print(f"⚠️ Impossible de sauvegarder l'état de validation: {validation_state}")
        
        if success:
            message = 'Artwork updated successfully'
            if validation_state:
                state_labels = {'validated': 'validée', 'rejected': 'rejetée', 'pending': 'en attente'}
                message += f' et image {state_labels.get(validation_state, validation_state)}'
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': 'Failed to update artwork'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 SERVEUR DE VALIDATION UNIFIÉ")
    print("=" * 50)
    print(f"📁 Dossier extractions: {EXTRACTIONS_DIR}")
    
    # Compter par type
    picasso_sessions = [s for s in validation_server.sessions if s.get('is_picasso', False)]
    dubuffet_sessions = [s for s in validation_server.sessions if s.get('is_dubuffet', False)]
    
    print(f"🎭 Sessions Picasso: {len(picasso_sessions)}")
    print(f"🎨 Sessions Dubuffet: {len(dubuffet_sessions)}")
    print(f"📊 Total sessions: {len(validation_server.sessions)}")
    
    if validation_server.sessions:
        print("\n📋 Sessions récentes:")
        for i, session in enumerate(validation_server.sessions[:5], 1):
            collection_emoji = "🎨" if session.get('is_dubuffet') else "🎭"
            ocr_info = f", {session['ocr_artworks']} œuvres OCR" if session.get('has_ocr') else ""
            print(f"  {i}. {collection_emoji} {session['name']} ({session['total_pages']} pages{ocr_info})")
        if len(validation_server.sessions) > 5:
            print(f"  ... et {len(validation_server.sessions) - 5} autres")
    
    print("\n🌐 Interface unifiée accessible sur:")
    print("  http://localhost:5000")
    print("\n✨ Fonctionnalités:")
    print("  🎭 Picasso : Validation classique")
    print("  🎨 Dubuffet : Validation + OCR + JSON individuels")
    print("  🔧 Décalage de page corrigé automatiquement")
    print("  📱 Interface adaptative selon la collection")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
