# Migration vers l'Architecture Modulaire

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
