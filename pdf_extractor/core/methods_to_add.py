    def _is_duplicate_rectangle(self, new_rect: dict, existing_rects: list) -> bool:
        """Vérifie si un rectangle est un doublon"""
        # Implémentation directe de la logique de déduplication
        new_bbox = new_rect['bbox']
        new_x, new_y = new_bbox['x'], new_bbox['y']
        new_w, new_h = new_bbox['w'], new_bbox['h']
        
        for existing_rect in existing_rects:
            ex_bbox = existing_rect['bbox']
            ex_x, ex_y = ex_bbox['x'], ex_bbox['y']
            ex_w, ex_h = ex_bbox['w'], ex_bbox['h']
            
            # Calculer le centre de chaque rectangle
            new_center = (new_x + new_w/2, new_y + new_h/2)
            ex_center = (ex_x + ex_w/2, ex_y + ex_h/2)
            
            # Distance entre les centres
            center_distance = np.sqrt((new_center[0] - ex_center[0])**2 + 
                                     (new_center[1] - ex_center[1])**2)
            
            # Si les centres sont très proches ET les tailles similaires
            max_dim = max(new_w, new_h, ex_w, ex_h)
            if center_distance < max_dim * 0.15:
                # Vérifier aussi la similarité des tailles
                size_ratio_w = min(new_w, ex_w) / max(new_w, ex_w)
                size_ratio_h = min(new_h, ex_h) / max(new_h, ex_h)
                
                if size_ratio_w > 0.8 and size_ratio_h > 0.8:
                    return True
            
            # Fallback: méthode de chevauchement classique
            left = max(new_x, ex_x)
            top = max(new_y, ex_y)
            right = min(new_x + new_w, ex_x + ex_w)
            bottom = min(new_y + new_h, ex_y + ex_h)
            
            if left < right and top < bottom:
                intersection = (right - left) * (bottom - top)
                area1 = new_w * new_h
                area2 = ex_w * ex_h
                
                # Si plus de 70% de chevauchement, c'est un doublon
                overlap_ratio = intersection / min(area1, area2)
                if overlap_ratio > 0.7:
                    return True
        
        return False
    
    def _create_page_text_details(self, page_dir: str, page_result: dict):
        """Crée un fichier texte avec les détails de la page"""
        details_path = os.path.join(page_dir, "README_ULTRA.txt")
        
        content = f"""PAGE {page_result['page_number']} - EXTRACTION ULTRA SENSIBLE
{'=' * 60}

MODE: ULTRA SENSIBLE - Capture TOUT !
- Statut: {'✅ Succès' if page_result['success'] else '❌ Échec'}
- Temps de traitement: {page_result['processing_time']}s
- Images extraites: {page_result['images_extracted']}
- Rectangles détectés: {page_result['rectangles_found']}
- DPI utilisé: {page_result.get('dpi_used', 'N/A')}

ANALYSE DE PAGE:
- Format: {page_result.get('page_analysis', {}).get('page_format', 'N/A')}
- Taille physique: {page_result.get('page_analysis', {}).get('width_mm', 0):.1f}×{page_result.get('page_analysis', {}).get('height_mm', 0):.1f}mm
- Taille image: {page_result.get('image_size', 'N/A')}
- Mégapixels: {page_result.get('image_megapixels', 0)}MP

IMAGES EXTRAITES:
"""
        
        if page_result['images_saved']:
            for i, img_name in enumerate(page_result['images_saved'], 1):
                details = next((r for r in page_result.get('rectangles_details', []) 
                              if r['filename'] == img_name), {})
                
                content += f"""
{i:2d}. {img_name}
    - Numéro d'œuvre: {details.get('artwork_number', 'Aucun')}
    - Taille: {details.get('size_kb', 0)} KB
    - Méthode détection: {details.get('detection_method', 'N/A')}
    - Confiance: {details.get('confidence', 0):.2f}
    - Miniature: {details.get('thumbnail', 'N/A')}
"""
        else:
            content += "\nAucune image extraite (page vide ou erreur).\n"
        
        if page_result.get('error'):
            content += f"\nERREUR:\n{page_result['error']}\n"
        
        content += f"""
Extraction ULTRA effectuée le {page_result.get('start_time', 'N/A')}
"""
        
        with open(details_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_text_summary(self, global_log: dict):
        """Crée un résumé texte global"""
        summary_path = os.path.join(self.session_dir, "RÉSUMÉ_ULTRA.txt")
        
        content = f"""EXTRACTION PDF ULTRA SENSIBLE - RÉSUMÉ COMPLET
{'=' * 70}

🎯 MODE ULTRA SENSIBLE - CAPTURE TOUT !

FICHIER SOURCE:
- Nom: {global_log['pdf_name']}
- Chemin: {global_log['pdf_path']}

EXTRACTION ULTRA:
- Début: {global_log['start_time']}
- Fin: {global_log['end_time']}

RÉSULTATS ULTRA:
- Pages traitées: {global_log['total_pages']}
- Pages réussies: {global_log['success_pages']}
- Pages échouées: {global_log['failed_pages']}
- Images extraites: {global_log['total_images_extracted']} ⚡ ULTRA SENSIBLE

🎉 RÉSULTAT: {global_log['total_images_extracted']} images extraites avec le mode ULTRA !
   Aucune image ne devrait être ratée avec cette méthode.
"""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(content)
