"""
Configuration centralisée pour l'extracteur PDF
"""
import os
from pathlib import Path

# Chemins de base
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_BASE_DIR = "extractions_ultra"

# Configuration Tesseract
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe", 
    r"C:\Users\lburg\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    r"C:\tesseract\tesseract.exe"
]

# Configuration Ollama
OLLAMA_CONFIG = {
    'url': "http://localhost:11434/api/generate",
    'model': "llava",
    'timeout': 30,
    'max_retries': 3
}

# Configuration Mistral
MISTRAL_CONFIG = {
    'api_key': None,  # À définir dans les variables d'environnement
    'model': "mistral-large-latest",
    'timeout': 30,
    'max_tokens': 2000,
    'temperature': 0.1
}

# Configuration de détection
DETECTION_CONFIG = {
    'ultra_configs': [
        {'name': 'ultra_micro', 'sensitivity': 90, 'mode': 'general', 'min_area_div': 1000},
        {'name': 'ultra_high_contrast', 'sensitivity': 20, 'mode': 'high_contrast', 'min_area_div': 800},
        {'name': 'ultra_documents', 'sensitivity': 80, 'mode': 'documents', 'min_area_div': 600},
        {'name': 'ultra_adaptive', 'sensitivity': 60, 'mode': 'general', 'min_area_div': 400},
        {'name': 'ultra_extreme', 'sensitivity': 95, 'mode': 'general', 'min_area_div': 2000},
    ],
    'max_rectangles_per_config': 50,
    'min_image_size': (20, 20),
    'thumbnail_size': 200
}

# Configuration OCR
OCR_CONFIG = {
    'psm_configs': [
        '--psm 7 -c tessedit_char_whitelist=0123456789NnOo°figFIGPlpl.:',
        '--psm 6 -c tessedit_char_whitelist=0123456789NnOo°figFIGPlpl.:',
        '--psm 8 -c tessedit_char_whitelist=0123456789',
    ],
    'scale_factor': 3.0,
    'max_number_length': 4,
    'min_number_length': 1
}

# Configuration de cohérence
COHERENCE_CONFIG = {
    'min_numbers_for_analysis': 2,
    'max_gap_threshold': 10,
    'duplicate_threshold': 0.7
}

# Configuration de logging
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'file': 'extraction.log'
}
