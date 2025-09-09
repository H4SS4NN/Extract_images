"""
Extracteur PDF Ultra Sensible - Architecture Modulaire

Un extracteur PDF professionnel avec architecture modulaire pour capturer
toutes les images, même les plus petites ou peu contrastées.

Modules:
- core: Classes principales (PDFExtractor)
- detectors: Détecteurs de rectangles (Ultra, Template, Color)
- analyzers: Analyseurs (Cohérence, Qualité)
- utils: Utilitaires (Logger, Image, File)
- config: Configuration centralisée

Usage:
    from pdf_extractor import PDFExtractor
    
    extractor = PDFExtractor()
    success = extractor.extract_pdf("document.pdf")
"""

__version__ = "2.0.0"
__author__ = "PDF Extractor Team"

from .core import PDFExtractor
from .utils import logger

__all__ = ['PDFExtractor', 'logger']
