#!/usr/bin/env python3
"""
Script de lancement rapide pour l'extracteur PDF
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

if __name__ == "__main__":
    from main import main
    main()
