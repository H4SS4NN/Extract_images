"""
Gestionnaire de logging centralisé
"""
import logging
import os
from datetime import datetime
from config import LOGGING_CONFIG

class Logger:
    """Gestionnaire de logging centralisé"""
    
    def __init__(self, name: str = None):
        self.logger = logging.getLogger(name or __name__)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure le logger"""
        if not self.logger.handlers:
            # Handler pour la console
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, LOGGING_CONFIG['level']))
            
            # Formatter
            formatter = logging.Formatter(LOGGING_CONFIG['format'])
            console_handler.setFormatter(formatter)
            
            # Ajouter le handler
            self.logger.addHandler(console_handler)
            self.logger.setLevel(getattr(logging, LOGGING_CONFIG['level']))
    
    def info(self, message: str):
        """Log info"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug"""
        self.logger.debug(message)
    
    def success(self, message: str):
        """Log success (info avec emoji)"""
        self.logger.info(f"✅ {message}")
    
    def failure(self, message: str):
        """Log failure (error avec emoji)"""
        self.logger.error(f"❌ {message}")

# Instance globale
logger = Logger()
