#!/usr/bin/env python3
"""
Serveur Flask pour l'interface de validation des extractions PDF ULTRA
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

class ValidationServer:
    def __init__(self):
        self.current_session = None
        self.sessions = self.scan_sessions()
    
    def scan_sessions(self):
        """Scanner toutes les sessions d'extraction ULTRA disponibles"""
        sessions = []
        
        if not os.path.exists(EXTRACTIONS_DIR):
            return sessions
        
        for session_dir in os.listdir(EXTRACTIONS_DIR):
            session_path = os.path.join(EXTRACTIONS_DIR, session_dir)
            if os.path.isdir(session_path):
                # Lire les métadonnées de la session
                meta_file = os.path.join(session_path, "extraction_ultra_complete.json")
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        sessions.append({
                            'name': session_dir,
                            'path': session_path,
                            'pdf_name': meta.get('pdf_name', 'Inconnu'),
                            'total_pages': int(meta.get('total_pages', 0) or 0),
                            'total_images': int(meta.get('total_images_extracted', 0) or 0),
                            'start_time': meta.get('start_time', ''),
                            'mode': meta.get('mode', 'ULTRA_SENSIBLE')
                        })
                    except Exception as e:
                        print(f"Erreur lecture métadonnées {session_dir}: {e}")
        
        # Trier par date (plus récent en premier)
        try:
            sessions.sort(key=lambda x: x.get('start_time') or '', reverse=True)
        except Exception:
            pass
        return sessions
    
    def get_page_images(self, session_name, page_num):
        """Récupérer toutes les images d'une page"""
        session_path = os.path.join(EXTRACTIONS_DIR, session_name)
        page_dir = os.path.join(session_path, f"page_{page_num:03d}")
        
        if not os.path.exists(page_dir):
            return []
        
        images = []
        
        # Lire les détails de la page si disponibles
        page_details_file = os.path.join(page_dir, "page_ultra_details.json")
        page_details = {}
        page_width = 0
        page_height = 0
        page_dpi = 0
        if os.path.exists(page_details_file):
            try:
                with open(page_details_file, 'r', encoding='utf-8') as f:
                    page_details = json.load(f)
                # Extraire meta de taille
                size_str = page_details.get('image_size') or ''
                if isinstance(size_str, str) and '×' in size_str:
                    try:
                        w_str, h_str = size_str.split('×')
                        page_width = int(w_str)
                        page_height = int(h_str)
                    except Exception:
                        page_width = page_height = 0
                page_dpi = int(page_details.get('dpi_used') or 0)
            except:
                pass
        
        rectangles_details = page_details.get('rectangles_details', [])
        
        # Scanner les images normales
        for img_file in glob.glob(os.path.join(page_dir, "*.png")):
            if "thumb_" in os.path.basename(img_file):
                continue  # Ignorer les miniatures
            
            filename = os.path.basename(img_file)
            
            # Trouver les détails correspondants
            details = next((r for r in rectangles_details if r.get('filename') == filename), {})
            
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
                'folder': 'normal'
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
                    'folder': 'DOUTEUX'
                })
        
        # Trier par nom de fichier
        images.sort(key=lambda x: x['filename'])
        # Injecter meta de page en tête de liste comme dict spécial
        return images, {
            'page_width': page_width,
            'page_height': page_height,
            'page_dpi': page_dpi
        }

# Instance globale du serveur
validation_server = ValidationServer()

@app.route('/')
def index():
    """Page principale - servir l'interface HTML"""
    return send_file('Interfacedecomparaison.html')

@app.route('/api/sessions')
def get_sessions():
    """Récupérer la liste de toutes les sessions disponibles"""
    # Re-scan automatique à chaque appel pour inclure les nouvelles sessions
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
        # Utiliser la première session disponible si aucune sélection côté client
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
        'path': session['path']
    })

@app.route('/api/get-page-images/<int:page_num>')
def get_page_images(page_num):
    """Récupérer les images d'une page spécifique"""
    # Fallback: choisir première session si aucune active
    if not validation_server.current_session:
        validation_server.sessions = validation_server.scan_sessions()
        if validation_server.sessions:
            validation_server.current_session = validation_server.sessions[0]
        else:
            return jsonify({'error': 'Aucune session active'}), 400
    
    session_name = validation_server.current_session['name']
    images, page_meta = validation_server.get_page_images(session_name, page_num)
    
    return jsonify({
        'page': page_num,
        'session': session_name,
        'images': images,
        'count': len(images),
        'meta': page_meta
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
                    
                    # DEBUG: Log pour vérifier la cohérence des numéros de pages
                    print(f"🔍 DEBUG: Page extraction {page_num} → PDF page {pdf_page_num} depuis {pdf_path}")
                    
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
                    logger.error(f"Erreur conversion PDF page {page_num}: {e}")
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
            logger.error(f"Erreur lecture métadonnées: {e}")
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
    """Sauvegarder les résultats de validation"""
    try:
        data = request.get_json()
        
        if not validation_server.current_session:
            return jsonify({'error': 'Aucune session active'}), 400
        
        # Créer le fichier de résultats
        session_path = validation_server.current_session['path']
        results_file = os.path.join(session_path, "validation_results.json")
        
        # Ajouter des métadonnées
        validation_data = {
            'session_name': data.get('sessionName'),
            'validation_timestamp': datetime.now().isoformat(),
            'total_pages': data.get('totalPages'),
            'image_states': data.get('imageStates', {}),
            'summary': data.get('summary', {}),
            'validator_info': {
                'version': '1.0',
                'interface': 'Web Validation Interface'
            }
        }
        
        # Sauvegarder
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Validation sauvegardée avec succès',
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
        export_dir = os.path.join(session_path, "VALIDATED_IMAGES")
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
            'message': f'{validated_count} images validées exportées',
            'export_dir': export_dir,
            'count': validated_count
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur export: {str(e)}'
        }), 500

@app.route('/api/retry-doubtful', methods=['POST'])
def retry_doubtful():
    """Relancer un post-traitement simple sur les images douteuses d'une page.
    Ici on applique un renforcement de contraste + légère netteté et on sauve
    une version _RETRY dans le même dossier DOUTEUX.
    """
    try:
        data = request.get_json() or {}
        page_num = int(data.get('page'))
        if not validation_server.current_session:
            return jsonify({'success': False, 'error': 'Aucune session active'}), 400

        import cv2
        import numpy as np

        session_path = validation_server.current_session['path']
        page_dir = os.path.join(session_path, f"page_{page_num:03d}")
        doubtful_dir = os.path.join(page_dir, 'DOUTEUX')
        if not os.path.exists(doubtful_dir):
            return jsonify({'success': True, 'processed': 0})

        processed = 0
        for name in os.listdir(doubtful_dir):
            if name.lower().endswith('.png') and name.startswith('DOUTEUX_'):
                src_path = os.path.join(doubtful_dir, name)
                img = cv2.imread(src_path, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                # Renforcement simple: CLAHE sur L, unsharp mask léger
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                l2 = clahe.apply(l)
                lab2 = cv2.merge((l2, a, b))
                enh = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
                # Unsharp
                blur = cv2.GaussianBlur(enh, (0,0), 1.0)
                sharp = cv2.addWeighted(enh, 1.3, blur, -0.3, 0)
                out_path = os.path.join(doubtful_dir, name.replace('.png', '_RETRY.png'))
                cv2.imwrite(out_path, sharp)
                processed += 1

        return jsonify({'success': True, 'processed': processed})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/refresh-sessions')
def refresh_sessions():
    """Rescanner les sessions disponibles"""
    validation_server.sessions = validation_server.scan_sessions()
    return jsonify({
        'success': True,
        'sessions': validation_server.sessions,
        'count': len(validation_server.sessions)
    })

@app.route('/api/stats')
def get_stats():
    """Statistiques globales"""
    total_sessions = len(validation_server.sessions)
    total_pages = sum(s['total_pages'] for s in validation_server.sessions)
    total_images = sum(s['total_images'] for s in validation_server.sessions)
    
    return jsonify({
        'total_sessions': total_sessions,
        'total_pages': total_pages,
        'total_images': total_images,
        'current_session': validation_server.current_session['name'] if validation_server.current_session else None
    })

@app.route('/api/redetect-crop', methods=['POST'])
def redetect_crop():
    """Recadre une zone (bbox) de la page PDF avec un padding optionnel et enregistre l'image.
    Body JSON: { page: int, bbox: {x,y,w,h}, pad: int, filename?: str }
    Retourne: { success, path, width, height }
    """
    try:
        data = request.get_json() or {}
        page_num = int(data.get('page'))
        bbox = data.get('bbox') or {}
        pad = int(data.get('pad') or 0)
        req_filename = data.get('filename')  # pour nommer la sortie

        if not validation_server.current_session:
            return jsonify({'success': False, 'error': 'Aucune session active'}), 400

        session_path = validation_server.current_session['path']
        page_dir = os.path.join(session_path, f"page_{page_num:03d}")
        meta_file = os.path.join(session_path, 'extraction_ultra_complete.json')
        page_details_file = os.path.join(page_dir, 'page_ultra_details.json')

        if not os.path.exists(meta_file):
            return jsonify({'success': False, 'error': 'Métadonnées globales introuvables'}), 404

        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        pdf_path = meta.get('pdf_original_path') or meta.get('pdf_path')
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'success': False, 'error': 'PDF source introuvable'}), 404

        dpi = 300
        try:
            if os.path.exists(page_details_file):
                with open(page_details_file, 'r', encoding='utf-8') as f:
                    page_details = json.load(f)
                dpi = int(page_details.get('dpi_used') or dpi)
        except Exception:
            pass

        from pdf2image import convert_from_path
        from PIL import Image

        # CORRECTION: Mapper le numéro de page de l'extraction vers le numéro de page du PDF
        start_page = meta.get('start_page', 1)
        pdf_page_num = start_page + page_num - 1

        images = convert_from_path(pdf_path, dpi=dpi, first_page=pdf_page_num, last_page=pdf_page_num)
        if not images:
            return jsonify({'success': False, 'error': 'Conversion PDF échouée'}), 500

        pil_img = images[0]
        W, H = pil_img.size
        x = max(0, int(bbox.get('x', 0)) - pad)
        y = max(0, int(bbox.get('y', 0)) - pad)
        w = int(bbox.get('w', 0)) + 2 * pad
        h = int(bbox.get('h', 0)) + 2 * pad
        x2 = min(W, x + w)
        y2 = min(H, y + h)
        x = max(0, min(x, W))
        y = max(0, min(y, H))

        if x2 <= x or y2 <= y:
            return jsonify({'success': False, 'error': 'Bbox invalide'}), 400

        crop = pil_img.crop((x, y, x2, y2))
        # Enregistrer dans le dossier de la page
        base_name = req_filename or f"bbox_{x}_{y}_{w}_{h}.png"
        out_name = f"REDETECT_{base_name}"
        out_path = os.path.join(page_dir, out_name)
        crop.save(out_path, format='PNG')

        rel_path = os.path.relpath(out_path, EXTRACTIONS_DIR)
        return jsonify({'success': True, 'path': rel_path, 'width': crop.size[0], 'height': crop.size[1]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Serveur de validation PDF ULTRA")
    print("=" * 50)
    print(f"📁 Dossier extractions: {EXTRACTIONS_DIR}")
    print(f"📊 Sessions trouvées: {len(validation_server.sessions)}")
    
    if validation_server.sessions:
        print("\n📋 Sessions disponibles:")
        for i, session in enumerate(validation_server.sessions[:5], 1):
            print(f"  {i}. {session['name']} ({session['total_pages']} pages, {session['total_images']} images)")
        if len(validation_server.sessions) > 5:
            print(f"  ... et {len(validation_server.sessions) - 5} autres")
    
    print("\n🌐 Interface accessible sur:")
    print("  http://localhost:5000")
    print("\n🔧 Endpoints API disponibles:")
    print("  GET  /api/sessions - Liste des sessions")
    print("  GET  /api/get-session-data - Session active")
    print("  GET  /api/get-page-images/<page> - Images d'une page")
    print("  GET  /api/get-image/<path> - Servir une image")
    print("  POST /api/save-validation - Sauvegarder validation")
    print("  POST /api/export-validated-images - Exporter validées")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
