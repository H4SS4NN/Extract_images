"""
Script de migration depuis l'ancien extract_pdf_ultra_sensible.py
"""
import os
import shutil
from pathlib import Path

def migrate_from_old():
    """Migre depuis l'ancien script vers la nouvelle architecture"""
    
    # Chemin vers l'ancien script
    old_script_path = Path(__file__).parent.parent / "extract_pdf_ultra_sensible.py"
    
    if not old_script_path.exists():
        print("❌ Ancien script non trouvé. Migration impossible.")
        return False
    
    # Créer un backup
    backup_path = old_script_path.with_suffix('.py.backup')
    shutil.copy2(old_script_path, backup_path)
    print(f"✅ Backup créé: {backup_path}")
    
    # Créer un script de compatibilité
    compatibility_script = old_script_path.parent / "extract_pdf_ultra_sensible_v2.py"
    
    compatibility_content = '''#!/usr/bin/env python3
"""
Script de compatibilité - Utilise la nouvelle architecture modulaire
"""

import sys
from pathlib import Path

# Ajouter le répertoire pdf_extractor au path
pdf_extractor_path = Path(__file__).parent / "pdf_extractor"
sys.path.insert(0, str(pdf_extractor_path))

from core import PDFExtractor
from utils import logger

def main():
    """Fonction principale - Compatible avec l'ancien script"""
    print("🚀 EXTRACTEUR PDF ULTRA SENSIBLE v2.0")
    print("=" * 60)
    print("🎯 MODE ULTRA : CAPTURE VRAIMENT TOUT !")
    print("✨ Architecture modulaire - Code maintenable")
    print("🔬 Multi-détection, seuils ultra-bas, DPI élevé")
    print("☁️ Spécialisé pour fonds clairs et balance des blancs")
    print("🎨 Détection par saturation et contours doux")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Intégration Ollama pour correction automatique")
    print("=" * 60)
    
    # Demander le fichier PDF
    pdf_path = input("📁 Chemin du fichier PDF: ").strip().strip('"')
    
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ Fichier non trouvé!")
        return
    
    # Demander la page de départ (optionnel)
    start_page_input = input("🔢 Page de départ (1 par défaut): ").strip()
    start_page = 1
    if start_page_input and start_page_input.isdigit():
        start_page = int(start_page_input)
    
    # Demander le nombre de pages (optionnel)
    max_pages_input = input("📄 Nombre max de pages (Entrée = jusqu'à la fin): ").strip()
    max_pages = None
    if max_pages_input and max_pages_input.isdigit():
        max_pages = int(max_pages_input)
    
    # Créer l'extracteur ULTRA
    extractor = PDFExtractor()
    
    # Lancer l'extraction ULTRA
    print("\\n🚀 Extraction ULTRA en cours...")
    print("⚡ Chaque page testée avec 8+ méthodes différentes")
    print("🔬 Seuils ultra-permissifs, DPI élevé")
    print("☁️ Optimisé pour fonds clairs et balance des blancs")
    print("🔍 Analyse de cohérence des numéros d'œuvres")
    print("🤖 Correction automatique avec Ollama si disponible")
    
    success = extractor.extract_pdf(pdf_path, max_pages, start_page)
    
    if success:
        print("\\n✅ Extraction ULTRA terminée avec succès!")
        print(f"📁 Résultats: {extractor.session_dir}")
        print("🎯 Mode ULTRA: Toutes les images devraient être capturées !")
    else:
        print("\\n❌ Extraction ULTRA échouée!")

if __name__ == "__main__":
    main()
'''
    
    with open(compatibility_script, 'w', encoding='utf-8') as f:
        f.write(compatibility_content)
    
    print(f"✅ Script de compatibilité créé: {compatibility_script}")
    
    # Créer un README de migration
    migration_readme = old_script_path.parent / "MIGRATION_README.md"
    
    migration_content = '''# Migration vers l'Architecture Modulaire

## 🎯 Nouvelle Architecture

L'ancien script `extract_pdf_ultra_sensible.py` a été refactorisé en architecture modulaire :

```
pdf_extractor/
├── core/                   # Classes principales
├── detectors/              # Détecteurs de rectangles
├── analyzers/              # Analyseurs
├── utils/                  # Utilitaires
├── config/                 # Configuration
└── tests/                  # Tests unitaires
```

## 🚀 Utilisation

### Option 1: Nouveau script principal
```bash
python pdf_extractor/main.py
```

### Option 2: Script de compatibilité
```bash
python extract_pdf_ultra_sensible_v2.py
```

### Option 3: Import Python
```python
from pdf_extractor import PDFExtractor

extractor = PDFExtractor()
success = extractor.extract_pdf("document.pdf")
```

## 📁 Fichiers

- `extract_pdf_ultra_sensible.py.backup` : Backup de l'ancien script
- `extract_pdf_ultra_sensible_v2.py` : Script de compatibilité
- `pdf_extractor/` : Nouvelle architecture modulaire

## ✅ Avantages de la Nouvelle Architecture

- **Code maintenable** : Séparation des responsabilités
- **Extensible** : Facile d'ajouter de nouveaux détecteurs
- **Testable** : Tests unitaires inclus
- **Configurable** : Configuration centralisée
- **Documenté** : Documentation complète

## 🔄 Migration

1. L'ancien script est sauvegardé en `.backup`
2. Utilisez le nouveau script principal ou le script de compatibilité
3. Tous les paramètres sont maintenant dans `config/settings.py`

## 🆘 Support

En cas de problème :
1. Vérifiez que tous les modules sont installés
2. Consultez la documentation dans `pdf_extractor/README.md`
3. Vérifiez les logs détaillés
'''
    
    with open(migration_readme, 'w', encoding='utf-8') as f:
        f.write(migration_content)
    
    print(f"✅ README de migration créé: {migration_readme}")
    print("\n🎉 Migration terminée !")
    print("\n📖 Consultez MIGRATION_README.md pour plus d'informations")
    
    return True

if __name__ == "__main__":
    migrate_from_old()
