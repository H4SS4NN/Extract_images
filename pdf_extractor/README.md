# Extracteur PDF Ultra Sensible

Un extracteur PDF professionnel avec architecture modulaire pour capturer toutes les images, même les plus petites ou peu contrastées.

## 🎯 Fonctionnalités

- **Multi-détection** : 8+ algorithmes par page
- **Seuils ultra-permissifs** : Capture vraiment tout
- **DPI élevé** : 400+ DPI pour plus de précision
- **Analyse de cohérence** : Vérification des numéros d'œuvres
- **Intégration Ollama** : Correction automatique avec IA
- **Analyse de sommaires** : Détecte et analyse les sommaires de catalogues
- **Extraction d'informations d'œuvres** : Utilise Mistral pour structurer les données
- **Architecture modulaire** : Code maintenable et extensible

## 🏗️ Architecture

```
pdf_extractor/
├── core/                   # Classes principales
│   ├── pdf_extractor.py   # Extracteur principal
│   └── __init__.py
├── detectors/              # Détecteurs de rectangles
│   ├── base_detector.py   # Classe de base
│   ├── ultra_detector.py  # Détecteur ultra sensible
│   ├── template_detector.py # Détecteur par template
│   ├── color_detector.py  # Détecteur par couleur
│   └── __init__.py
├── analyzers/              # Analyseurs
│   ├── coherence_analyzer.py # Analyse de cohérence
│   ├── quality_analyzer.py   # Analyse de qualité
│   └── __init__.py
├── utils/                  # Utilitaires
│   ├── logger.py          # Gestionnaire de logs
│   ├── image_utils.py     # Utilitaires d'images
│   ├── file_utils.py      # Utilitaires de fichiers
│   └── __init__.py
├── config/                 # Configuration
│   ├── settings.py        # Paramètres
│   └── __init__.py
├── tests/                  # Tests unitaires
├── main.py                # Point d'entrée
├── requirements.txt       # Dépendances
└── README.md             # Documentation
```

## 🚀 Installation

1. **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

2. **Installer Tesseract OCR** :
- Windows : Télécharger depuis [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
- Le script détectera automatiquement l'installation

3. **Installer Ollama (optionnel)** :
```bash
# Installer Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger le modèle LLaVA
ollama pull llava
```

## 📖 Usage

### Utilisation simple

```python
from pdf_extractor import PDFExtractor

# Créer l'extracteur
extractor = PDFExtractor()

# Extraire un PDF
success = extractor.extract_pdf("document.pdf")

if success:
    print(f"Résultats dans : {extractor.session_dir}")
```

### Utilisation avancée

```python
from pdf_extractor import PDFExtractor

# Créer l'extracteur
extractor = PDFExtractor()

# Extraire avec paramètres
success = extractor.extract_pdf(
    pdf_path="document.pdf",
    max_pages=10,      # Limiter à 10 pages
    start_page=5       # Commencer à la page 5
)
```

### Utilisation en ligne de commande

```bash
python main.py
```

## 🔧 Configuration

Tous les paramètres sont centralisés dans `config/settings.py` :

- **TESSERACT_PATHS** : Chemins de recherche de Tesseract
- **OLLAMA_CONFIG** : Configuration Ollama
- **DETECTION_CONFIG** : Paramètres de détection
- **OCR_CONFIG** : Configuration OCR
- **COHERENCE_CONFIG** : Paramètres de cohérence

## 🧪 Tests

```bash
# Lancer les tests
python -m pytest tests/

# Tests avec couverture
python -m pytest tests/ --cov=pdf_extractor
```

## 📊 Résultats

L'extracteur génère :

- **Images extraites** : PNG haute qualité
- **Miniatures** : Thumbnails 200px
- **Images douteuses** : Dossier séparé avec explications
- **Logs détaillés** : JSON et TXT
- **Analyse de cohérence** : Vérification des numéros

## 🤖 Intégration Ollama

Pour utiliser l'analyse IA :

1. Installer Ollama
2. Télécharger LLaVA : `ollama pull llava`
3. Démarrer le serveur : `ollama serve`
4. L'extracteur détectera automatiquement Ollama

## 🔍 Détecteurs Disponibles

- **UltraDetector** : Multi-configurations ultra sensibles
- **TemplateDetector** : Matching de templates
- **ColorDetector** : Analyse de couleur et contraste

## 📈 Analyseurs

- **CoherenceAnalyzer** : Vérification des numéros d'œuvres
- **QualityAnalyzer** : Classification des images douteuses

## 🛠️ Développement

### Ajouter un nouveau détecteur

```python
from detectors.base_detector import BaseDetector

class MonDetecteur(BaseDetector):
    def __init__(self):
        super().__init__("mon_detecteur")
    
    def detect(self, image, config=None):
        # Implémenter la détection
        return rectangles
```

### Ajouter un nouvel analyseur

```python
class MonAnalyseur:
    def __init__(self):
        self.logger = logger
    
    def analyze(self, data):
        # Implémenter l'analyse
        return result
```

## 📝 Changelog

### v2.0.0
- Architecture modulaire complète
- Séparation des responsabilités
- Code maintenable et extensible
- Tests unitaires
- Documentation complète

### v1.0.0
- Extraction ultra sensible
- Multi-détection
- Analyse de cohérence
- Intégration Ollama

## 📄 Licence

MIT License - Voir le fichier LICENSE pour plus de détails.

## 🤝 Contribution

Les contributions sont les bienvenues ! Merci de :

1. Fork le projet
2. Créer une branche feature
3. Commiter les changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📞 Support

Pour toute question ou problème :

- Ouvrir une issue sur GitHub
- Consulter la documentation
- Vérifier les logs détaillés
