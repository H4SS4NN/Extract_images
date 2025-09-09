#!/usr/bin/env python3
"""
Script de lancement principal pour l'extracteur PDF
Utilise la nouvelle architecture modulaire
"""
import sys
from pathlib import Path

# Ajouter le répertoire pdf_extractor au path
pdf_extractor_path = Path(__file__).parent / "pdf_extractor"
sys.path.insert(0, str(pdf_extractor_path))

if __name__ == "__main__":
    from main import main
    main()
