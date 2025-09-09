"""
Tests de base pour l'extracteur PDF
"""
import unittest
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent.parent))

from pdf_extractor.core import PDFExtractor
from pdf_extractor.utils import ImageUtils, FileUtils
from pdf_extractor.detectors import UltraDetector, TemplateDetector, ColorDetector
from pdf_extractor.analyzers import CoherenceAnalyzer, QualityAnalyzer

class TestPDFExtractor(unittest.TestCase):
    """Tests pour l'extracteur PDF principal"""
    
    def setUp(self):
        """Configuration des tests"""
        self.extractor = PDFExtractor()
    
    def test_extractor_initialization(self):
        """Test l'initialisation de l'extracteur"""
        self.assertIsNotNone(self.extractor)
        self.assertIsNotNone(self.extractor.detectors)
        self.assertIsNotNone(self.extractor.coherence_analyzer)
        self.assertIsNotNone(self.extractor.quality_analyzer)
    
    def test_session_folder_creation(self):
        """Test la création du dossier de session"""
        session_dir = FileUtils.create_session_folder("test.pdf", "test_output")
        self.assertTrue(os.path.exists(session_dir))
        self.assertIn("test_ULTRA_", session_dir)
    
    def test_page_folder_creation(self):
        """Test la création du dossier de page"""
        session_dir = "test_session"
        os.makedirs(session_dir, exist_ok=True)
        
        page_dir = FileUtils.create_page_folder(session_dir, 1)
        self.assertTrue(os.path.exists(page_dir))
        self.assertIn("page_001", page_dir)
        
        # Nettoyer
        os.rmdir(page_dir)
        os.rmdir(session_dir)

class TestDetectors(unittest.TestCase):
    """Tests pour les détecteurs"""
    
    def setUp(self):
        """Configuration des tests"""
        import numpy as np
        # Créer une image de test
        self.test_image = np.ones((200, 300, 3), dtype=np.uint8) * 255
        # Ajouter un rectangle simple
        self.test_image[50:150, 100:200] = [0, 0, 0]
    
    def test_ultra_detector(self):
        """Test le détecteur ultra"""
        detector = UltraDetector()
        rectangles = detector.detect(self.test_image)
        self.assertIsInstance(rectangles, list)
    
    def test_template_detector(self):
        """Test le détecteur par template"""
        detector = TemplateDetector()
        rectangles = detector.detect(self.test_image)
        self.assertIsInstance(rectangles, list)
    
    def test_color_detector(self):
        """Test le détecteur par couleur"""
        detector = ColorDetector()
        rectangles = detector.detect(self.test_image)
        self.assertIsInstance(rectangles, list)

class TestAnalyzers(unittest.TestCase):
    """Tests pour les analyseurs"""
    
    def test_coherence_analyzer(self):
        """Test l'analyseur de cohérence"""
        analyzer = CoherenceAnalyzer()
        
        # Test avec des numéros cohérents
        rectangles_details = [
            {'artwork_number': '1', 'bbox': {'x': 0, 'y': 0, 'w': 100, 'h': 100}},
            {'artwork_number': '2', 'bbox': {'x': 100, 'y': 0, 'w': 100, 'h': 100}},
            {'artwork_number': '3', 'bbox': {'x': 200, 'y': 0, 'w': 100, 'h': 100}}
        ]
        
        result = analyzer.analyze(rectangles_details)
        self.assertTrue(result['is_sequential'])
        self.assertEqual(result['detected_numbers'], [1, 2, 3])
    
    def test_quality_analyzer(self):
        """Test l'analyseur de qualité"""
        analyzer = QualityAnalyzer()
        
        import numpy as np
        # Image de test (blanche)
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        
        result = analyzer.analyze_image_quality(test_image, [test_image])
        self.assertTrue(result['is_doubtful'])
        self.assertIn('image_vide', result['reasons'])

class TestImageUtils(unittest.TestCase):
    """Tests pour les utilitaires d'images"""
    
    def test_thumbnail_creation(self):
        """Test la création de miniatures"""
        import numpy as np
        test_image = np.ones((400, 300, 3), dtype=np.uint8)
        
        thumbnail = ImageUtils.create_thumbnail(test_image, 200)
        self.assertEqual(thumbnail.shape[0], 200)
        self.assertEqual(thumbnail.shape[1], 150)
    
    def test_image_validation(self):
        """Test la validation d'images"""
        import numpy as np
        
        # Image valide
        valid_image = np.ones((100, 100, 3), dtype=np.uint8)
        self.assertTrue(ImageUtils.is_image_valid(valid_image))
        
        # Image trop petite
        small_image = np.ones((10, 10, 3), dtype=np.uint8)
        self.assertFalse(ImageUtils.is_image_valid(small_image))
        
        # Image None
        self.assertFalse(ImageUtils.is_image_valid(None))

if __name__ == '__main__':
    unittest.main()
