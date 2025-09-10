#!/usr/bin/env python3
"""
Serveur Flask pour l'interface de validation des extractions Dubuffet avec OCR
Extension du serveur de validation existant avec fonctionnalités OCR
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

class DubuffetValidationServer:
    def __init__(self):
        self.current_session = None
        self.sessions = self.scan_sessions()
    
    def scan_sessions(self):
        """Scanner toutes les sessions d'extraction Dubuffet disponibles"""
        sessions = []
        
        if not os.path.exists(EXTRACTIONS_DIR):
            return sessions
        
        for session_dir in os.listdir(EXTRACTIONS_DIR):
            session_path = os.path.join(EXTRACTIONS_DIR, session_dir)
            if os.path.isdir(session_path):
                # Vérifier si c'est une extraction Dubuffet
                is_dubuffet = "DUBUFFET" in session_dir.upper()
                
                # Lire les métadonnées de la session
                meta_file = os.path.join(session_path, "extraction_ultra_complete.json")
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        # Vérifier les résultats OCR Dubuffet
                        ocr_results = None
                        dubuffet_ocr_file = os.path.join(session_path, "dubuffet_ocr_results.json")
                        if os.path.exists(dubuffet_ocr_file):
                            try:
                                with open(dubuffet_ocr_file, 'r', encoding='utf-8') as f:
                                    ocr_results = json.load(f)
                            except:
                                pass
                        
                        # Compter les JSON d'œuvres individuelles
                        individual_jsons = len(list(Path(session_path).rglob("oeuvre_*.json")))
                        
                        sessions.append({
                            'name': session_dir,
                            'path': session_path,
                            'pdf_name': meta.get('pdf_name', 'Inconnu'),
                            'total_pages': int(meta.get('total_pages', 0) or 0),
                            'total_images': int(meta.get('total_images_extracted', 0) or 0),
                            'start_time': meta.get('start_time', ''),
                            'mode': meta.get('mode', 'ULTRA_SENSIBLE'),
                            'is_dubuffet': is_dubuffet,
                            'has_ocr': ocr_results is not None,
                            'ocr_artworks': len(ocr_results.get('artworks', {})) if ocr_results else 0,
                            'individual_jsons': individual_jsons
                        })
                    except Exception as e:
                        print(f"Erreur lecture métadonnées {session_dir}: {e}")
        
        # Trier par date (plus récent en premier)
        try:
            sessions.sort(key=lambda x: x.get('start_time') or '', reverse=True)
        except Exception:
            pass
        return sessions
    
    def get_page_images_with_ocr(self, session_name, page_num):
        """Récupérer toutes les images d'une page avec données OCR"""
        session_path = os.path.join(EXTRACTIONS_DIR, session_name)
        page_dir = os.path.join(session_path, f"page_{page_num:03d}")
        
        if not os.path.exists(page_dir):
            return [], {}
        
        images = []
        ocr_data = {}
        
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
            
            images.append({
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
                'folder': 'normal',
                # NOUVEAU: Données OCR
                'has_ocr': artwork_data is not None,
                'ocr_title': artwork_data.get('title') if artwork_data else None,
                'ocr_medium': artwork_data.get('medium') if artwork_data else None,
                'ocr_dimensions': artwork_data.get('dimensions_cm') if artwork_data else None,
                'ocr_date': artwork_data.get('date_text') if artwork_data else None,
                'ocr_confidence': artwork_data.get('ocr_confidence') if artwork_data else None,
                'ocr_region': artwork_data.get('ocr_region') if artwork_data else None,
                'artwork_json': os.path.basename(artwork_json_path) if artwork_json_path else None
            })
        
        # Scanner les images debug OCR
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
                    'has_ocr': False
                })
        
        # Trier par nom de fichier
        images.sort(key=lambda x: x['filename'])
        
        # Métadonnées de page avec OCR
        page_meta = {
            'page_width': 0,
            'page_height': 0,
            'page_dpi': 0,
            'ocr_debug_count': len(ocr_debug_images),
            'ocr_debug_images': ocr_debug_images
        }
        
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

# Instance globale du serveur
validation_server = DubuffetValidationServer()

@app.route('/')
def index():
    """Page principale - servir l'interface HTML Dubuffet"""
    return send_file('dubuffet_validation_interface.html')

@app.route('/api/sessions')
def get_sessions():
    """Récupérer la liste de toutes les sessions Dubuffet disponibles"""
    # Re-scan automatique à chaque appel
    try:
        validation_server.sessions = validation_server.scan_sessions()
    except Exception:
        pass
    
    # Filtrer les sessions Dubuffet
    dubuffet_sessions = [s for s in validation_server.sessions if s.get('is_dubuffet', False)]
    
    return jsonify({
        'sessions': dubuffet_sessions,
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
    dubuffet_sessions = [s for s in validation_server.sessions if s.get('is_dubuffet', False)]
    
    if not validation_server.current_session:
        # Utiliser la première session Dubuffet disponible
        if dubuffet_sessions:
            validation_server.current_session = dubuffet_sessions[0]
        else:
            return jsonify({'error': 'Aucune session Dubuffet disponible'}), 404
    
    session = validation_server.current_session
    return jsonify({
        'sessionName': session['name'],
        'pdfName': session['pdf_name'],
        'totalPages': session['total_pages'],
        'totalImages': session['total_images'],
        'mode': session['mode'],
        'startTime': session['start_time'],
        'path': session['path'],
        'isDubuffet': session.get('is_dubuffet', False),
        'hasOCR': session.get('has_ocr', False),
        'ocrArtworks': session.get('ocr_artworks', 0),
        'individualJsons': session.get('individual_jsons', 0)
    })

@app.route('/api/get-page-images/<int:page_num>')
def get_page_images(page_num):
    """Récupérer les images d'une page spécifique avec données OCR"""
    # Fallback: choisir première session Dubuffet si aucune active
    if not validation_server.current_session:
        validation_server.sessions = validation_server.scan_sessions()
        dubuffet_sessions = [s for s in validation_server.sessions if s.get('is_dubuffet', False)]
        if dubuffet_sessions:
            validation_server.current_session = dubuffet_sessions[0]
        else:
            return jsonify({'error': 'Aucune session Dubuffet active'}), 400
    
    session_name = validation_server.current_session['name']
    images, page_meta = validation_server.get_page_images_with_ocr(session_name, page_num)
    
    return jsonify({
        'page': page_num,
        'session': session_name,
        'images': images,
        'count': len(images),
        'meta': page_meta,
        'isDubuffet': True
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
    """Récupérer le JSON d'une œuvre spécifique"""
    if not validation_server.current_session:
        return jsonify({'error': 'Aucune session active'}), 400
    
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

@app.route('/api/get-ocr-results')
def get_ocr_results():
    """Récupérer les résultats OCR globaux de la session"""
    if not validation_server.current_session:
        return jsonify({'error': 'Aucune session active'}), 400
    
    session_path = validation_server.current_session['path']
    ocr_file = os.path.join(session_path, "dubuffet_ocr_results.json")
    
    if os.path.exists(ocr_file):
        try:
            with open(ocr_file, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            return jsonify(ocr_data)
        except:
            pass
    
    return jsonify({'error': 'Résultats OCR non trouvés'}), 404

# Hériter des autres endpoints du serveur de validation original
@app.route('/api/get-pdf-page/<int:page_num>')
def get_pdf_page(page_num):
    """Récupérer l'image de la page PDF originale"""
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
                    
                    # CORRECTION: Mapper le numéro de page de l'extraction vers le numéro de page du PDF
                    start_page = meta.get('start_page', 1)
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
                        'pdf_path': pdf_path
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

@app.route('/api/save-validation', methods=['POST'])
def save_validation():
    """Sauvegarder les résultats de validation Dubuffet"""
    try:
        data = request.get_json()
        
        if not validation_server.current_session:
            return jsonify({'error': 'Aucune session active'}), 400
        
        # Créer le fichier de résultats
        session_path = validation_server.current_session['path']
        results_file = os.path.join(session_path, "dubuffet_validation_results.json")
        
        # Ajouter des métadonnées
        validation_data = {
            'session_name': data.get('sessionName'),
            'validation_timestamp': datetime.now().isoformat(),
            'total_pages': data.get('totalPages'),
            'image_states': data.get('imageStates', {}),
            'ocr_validations': data.get('ocrValidations', {}),
            'summary': data.get('summary', {}),
            'validator_info': {
                'version': '2.0',
                'interface': 'Dubuffet Validation Interface',
                'collection': 'Jean Dubuffet'
            }
        }
        
        # Sauvegarder
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Validation Dubuffet sauvegardée avec succès',
            'file': results_file
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur sauvegarde: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🎨 SERVEUR DE VALIDATION DUBUFFET")
    print("=" * 50)
    print(f"📁 Dossier extractions: {EXTRACTIONS_DIR}")
    
    # Filtrer les sessions Dubuffet
    dubuffet_sessions = [s for s in validation_server.sessions if s.get('is_dubuffet', False)]
    print(f"🎭 Sessions Dubuffet trouvées: {len(dubuffet_sessions)}")
    
    if dubuffet_sessions:
        print("\n🎨 Sessions Dubuffet disponibles:")
        for i, session in enumerate(dubuffet_sessions[:5], 1):
            ocr_info = f", {session['ocr_artworks']} œuvres OCR" if session.get('has_ocr') else ", pas d'OCR"
            print(f"  {i}. {session['name']} ({session['total_pages']} pages, {session['total_images']} images{ocr_info})")
        if len(dubuffet_sessions) > 5:
            print(f"  ... et {len(dubuffet_sessions) - 5} autres")
    
    print("\n🌐 Interface Dubuffet accessible sur:")
    print("  http://localhost:5001")
    print("\n🔧 Endpoints API Dubuffet:")
    print("  GET  /api/sessions - Sessions Dubuffet")
    print("  GET  /api/get-page-images/<page> - Images + OCR")
    print("  GET  /api/get-artwork-json/<page>/<filename> - JSON œuvre")
    print("  GET  /api/get-ocr-results - Résultats OCR globaux")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
