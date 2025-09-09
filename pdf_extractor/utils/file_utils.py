"""
Utilitaires pour la gestion des fichiers
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

class FileUtils:
    """Utilitaires pour la gestion des fichiers"""
    
    @staticmethod
    def create_session_folder(pdf_name: str, output_base_dir: str) -> str:
        """Crée le dossier de session principal"""
        clean_name = os.path.splitext(pdf_name)[0]
        clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = f"{clean_name}_ULTRA_{timestamp}"
        
        session_dir = os.path.join(output_base_dir, session_name)
        os.makedirs(session_dir, exist_ok=True)
        
        return session_dir
    
    @staticmethod
    def create_page_folder(session_dir: str, page_num: int) -> str:
        """Crée un dossier pour une page spécifique"""
        page_dir = os.path.join(session_dir, f"page_{page_num:03d}")
        os.makedirs(page_dir, exist_ok=True)
        return page_dir
    
    @staticmethod
    def create_doubtful_folder(page_dir: str) -> str:
        """Crée le dossier pour les images douteuses"""
        doubtful_dir = os.path.join(page_dir, "DOUTEUX")
        os.makedirs(doubtful_dir, exist_ok=True)
        return doubtful_dir
    
    @staticmethod
    def get_file_size_kb(file_path: str) -> int:
        """Retourne la taille du fichier en KB"""
        try:
            return os.path.getsize(file_path) // 1024
        except:
            return 0
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """Nettoie un nom de fichier"""
        # Remplacer les caractères non valides
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limiter la longueur
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        return filename
    
    @staticmethod
    def ensure_directory_exists(directory: str) -> None:
        """S'assure qu'un répertoire existe"""
        os.makedirs(directory, exist_ok=True)
    
    @staticmethod
    def get_relative_path(file_path: str, base_path: str) -> str:
        """Retourne le chemin relatif d'un fichier"""
        try:
            return os.path.relpath(file_path, base_path)
        except:
            return file_path
