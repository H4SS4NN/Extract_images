"""
Module des détecteurs
"""
from .base_detector import BaseDetector
from .ultra_detector import UltraDetector
from .template_detector import TemplateDetector
from .color_detector import ColorDetector

__all__ = ['BaseDetector', 'UltraDetector', 'TemplateDetector', 'ColorDetector']
