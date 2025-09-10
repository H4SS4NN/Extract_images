#!/usr/bin/env python3
"""
Script de démonstration de l'architecture modulaire
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

def demo_architecture():
    """Démonstration de l'architecture modulaire"""
    print("🏗️ DÉMONSTRATION DE L'ARCHITECTURE MODULAIRE")
    print("=" * 60)
    
    # 1. Import des modules
    print("\n📦 1. Import des modules...")
    try:
        from core import PDFExtractor
        from detectors import UltraDetector, TemplateDetector, ColorDetector
        from analyzers import CoherenceAnalyzer, QualityAnalyzer
        from utils import logger, ImageUtils, FileUtils
        from config import DETECTION_CONFIG, OLLAMA_CONFIG
        print("✅ Tous les modules importés avec succès")
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    # 2. Création des instances
    print("\n🔧 2. Création des instances...")
    try:
        extractor = PDFExtractor()
        ultra_detector = UltraDetector()
        template_detector = TemplateDetector()
        color_detector = ColorDetector()
        coherence_analyzer = CoherenceAnalyzer()
        quality_analyzer = QualityAnalyzer()
        print("✅ Toutes les instances créées avec succès")
    except Exception as e:
        print(f"❌ Erreur de création: {e}")
        return False
    
    # 3. Test des détecteurs
    print("\n🔍 3. Test des détecteurs...")
    try:
        import numpy as np
        # Créer une image de test
        test_image = np.ones((200, 300, 3), dtype=np.uint8) * 255
        test_image[50:150, 100:200] = [0, 0, 0]  # Rectangle noir
        
        # Tester chaque détecteur
        ultra_rects = ultra_detector.detect(test_image)
        template_rects = template_detector.detect(test_image)
        color_rects = color_detector.detect(test_image)
        
        print(f"✅ UltraDetector: {len(ultra_rects)} rectangles")
        print(f"✅ TemplateDetector: {len(template_rects)} rectangles")
        print(f"✅ ColorDetector: {len(color_rects)} rectangles")
    except Exception as e:
        print(f"❌ Erreur de test des détecteurs: {e}")
        return False
    
    # 4. Test des analyseurs
    print("\n📊 4. Test des analyseurs...")
    try:
        # Test de cohérence
        rectangles_details = [
            {'artwork_number': '1', 'bbox': {'x': 0, 'y': 0, 'w': 100, 'h': 100}},
            {'artwork_number': '2', 'bbox': {'x': 100, 'y': 0, 'w': 100, 'h': 100}},
            {'artwork_number': '3', 'bbox': {'x': 200, 'y': 0, 'w': 100, 'h': 100}}
        ]
        
        coherence_result = coherence_analyzer.analyze(rectangles_details)
        print(f"✅ CoherenceAnalyzer: {coherence_result['is_sequential']}")
        
        # Test de qualité
        quality_result = quality_analyzer.analyze_image_quality(test_image, [test_image])
        print(f"✅ QualityAnalyzer: {quality_result['is_doubtful']}")
    except Exception as e:
        print(f"❌ Erreur de test des analyseurs: {e}")
        return False
    
    # 5. Test des utilitaires
    print("\n🛠️ 5. Test des utilitaires...")
    try:
        # Test ImageUtils
        thumbnail = ImageUtils.create_thumbnail(test_image)
        print(f"✅ ImageUtils: miniature {thumbnail.shape}")
        
        # Test FileUtils
        test_dir = FileUtils.create_session_folder("test.pdf", "test_output")
        print(f"✅ FileUtils: dossier créé {test_dir}")
        
        # Nettoyer
        import os
        if os.path.exists(test_dir):
            os.rmdir(test_dir)
    except Exception as e:
        print(f"❌ Erreur de test des utilitaires: {e}")
        return False
    
    # 6. Test de configuration
    print("\n⚙️ 6. Test de configuration...")
    try:
        print(f"✅ DETECTION_CONFIG: {len(DETECTION_CONFIG['ultra_configs'])} configs")
        print(f"✅ OLLAMA_CONFIG: {OLLAMA_CONFIG['model']}")
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        return False
    
    # 7. Test de logging
    print("\n📝 7. Test de logging...")
    try:
        logger.info("Test de logging")
        logger.success("Test de succès")
        logger.warning("Test d'avertissement")
        print("✅ Logger fonctionne correctement")
    except Exception as e:
        print(f"❌ Erreur de logging: {e}")
        return False
    
    print("\n🎉 DÉMONSTRATION TERMINÉE AVEC SUCCÈS !")
    print("=" * 60)
    print("✅ Architecture modulaire fonctionnelle")
    print("✅ Tous les composants opérationnels")
    print("✅ Prêt pour l'extraction PDF")
    
    return True

if __name__ == "__main__":
    success = demo_architecture()
    if not success:
        print("\n❌ La démonstration a échoué. Vérifiez les erreurs ci-dessus.")
        sys.exit(1)
    else:
        print("\n🚀 L'architecture est prête ! Utilisez 'python main.py' pour commencer.")
