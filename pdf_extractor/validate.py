#!/usr/bin/env python3
"""
Script de validation de l'architecture modulaire
"""
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))

def validate_architecture():
    """Valide que l'architecture modulaire est correcte"""
    print("🔍 VALIDATION DE L'ARCHITECTURE MODULAIRE")
    print("=" * 60)
    
    errors = []
    warnings = []
    
    # 1. Vérifier la structure des dossiers
    print("\n📁 1. Vérification de la structure...")
    required_dirs = [
        "core",
        "detectors", 
        "analyzers",
        "utils",
        "config",
        "tests"
    ]
    
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            errors.append(f"❌ Dossier manquant: {dir_name}")
        else:
            print(f"✅ {dir_name}/")
    
    # 2. Vérifier les fichiers principaux
    print("\n📄 2. Vérification des fichiers principaux...")
    required_files = [
        "core/pdf_extractor.py",
        "core/__init__.py",
        "detectors/__init__.py",
        "analyzers/__init__.py",
        "utils/__init__.py",
        "config/__init__.py",
        "main.py",
        "requirements.txt",
        "README.md"
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            errors.append(f"❌ Fichier manquant: {file_path}")
        else:
            print(f"✅ {file_path}")
    
    # 3. Vérifier les imports
    print("\n📦 3. Vérification des imports...")
    try:
        from core import PDFExtractor
        from detectors import UltraDetector, TemplateDetector, ColorDetector
        from analyzers import CoherenceAnalyzer, QualityAnalyzer
        from utils import logger, ImageUtils, FileUtils
        from config import DETECTION_CONFIG, OLLAMA_CONFIG
        print("✅ Tous les imports fonctionnent")
    except ImportError as e:
        errors.append(f"❌ Erreur d'import: {e}")
    
    # 4. Vérifier les classes principales
    print("\n🏗️ 4. Vérification des classes...")
    try:
        # Test PDFExtractor
        extractor = PDFExtractor()
        if not hasattr(extractor, 'extract_pdf'):
            errors.append("❌ PDFExtractor manque la méthode extract_pdf")
        else:
            print("✅ PDFExtractor")
        
        # Test détecteurs
        ultra = UltraDetector()
        template = TemplateDetector()
        color = ColorDetector()
        if not hasattr(ultra, 'detect'):
            errors.append("❌ UltraDetector manque la méthode detect")
        else:
            print("✅ Détecteurs")
        
        # Test analyseurs
        coherence = CoherenceAnalyzer()
        quality = QualityAnalyzer()
        if not hasattr(coherence, 'analyze'):
            errors.append("❌ CoherenceAnalyzer manque la méthode analyze")
        else:
            print("✅ Analyseurs")
        
        # Test utilitaires
        if not hasattr(ImageUtils, 'create_thumbnail'):
            errors.append("❌ ImageUtils manque la méthode create_thumbnail")
        else:
            print("✅ Utilitaires")
            
    except Exception as e:
        errors.append(f"❌ Erreur de création des classes: {e}")
    
    # 5. Vérifier la configuration
    print("\n⚙️ 5. Vérification de la configuration...")
    try:
        if not isinstance(DETECTION_CONFIG['ultra_configs'], list):
            errors.append("❌ DETECTION_CONFIG['ultra_configs'] n'est pas une liste")
        else:
            print(f"✅ Configuration: {len(DETECTION_CONFIG['ultra_configs'])} configs")
        
        if not isinstance(OLLAMA_CONFIG['model'], str):
            errors.append("❌ OLLAMA_CONFIG['model'] n'est pas une chaîne")
        else:
            print(f"✅ Ollama: {OLLAMA_CONFIG['model']}")
            
    except Exception as e:
        errors.append(f"❌ Erreur de configuration: {e}")
    
    # 6. Vérifier les tests
    print("\n🧪 6. Vérification des tests...")
    test_file = "tests/test_basic.py"
    if os.path.exists(test_file):
        print("✅ Tests unitaires présents")
    else:
        warnings.append("⚠️ Tests unitaires manquants")
    
    # 7. Vérifier la documentation
    print("\n📚 7. Vérification de la documentation...")
    if os.path.exists("README.md"):
        with open("README.md", 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1000:  # README substantiel
                print("✅ Documentation complète")
            else:
                warnings.append("⚠️ Documentation incomplète")
    else:
        errors.append("❌ README.md manquant")
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ ERREURS ({len(errors)}):")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print(f"\n⚠️ AVERTISSEMENTS ({len(warnings)}):")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors:
        print("\n🎉 VALIDATION RÉUSSIE !")
        print("✅ L'architecture modulaire est correcte")
        print("✅ Prêt pour la production")
        return True
    else:
        print(f"\n❌ VALIDATION ÉCHOUÉE ({len(errors)} erreurs)")
        print("🔧 Corrigez les erreurs avant de continuer")
        return False

if __name__ == "__main__":
    success = validate_architecture()
    if not success:
        sys.exit(1)
    else:
        print("\n🚀 L'architecture est validée et prête !")
