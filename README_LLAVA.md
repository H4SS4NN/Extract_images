# 🤖 Configuration LLaVA pour l'Extraction PDF ULTRA SENSIBLE

## 🎯 Vue d'ensemble

Le script `extract_pdf_ultra_sensible.py` utilise LLaVA (Large Language and Vision Assistant) via Ollama pour analyser visuellement les pages de catalogues d'art et détecter les incohérences dans la numérotation des œuvres.

## 🚀 Démarrage Rapide

### Option 1: Script de démarrage automatique
```bash
python start_extraction.py
```
Ce script vérifie automatiquement toutes les dépendances et lance l'extraction.

### Option 2: Démarrage manuel
```bash
python extract_pdf_ultra_sensible.py
```

## 🔧 Installation d'Ollama et LLaVA

### 1. Installer Ollama
- Téléchargez depuis: https://ollama.ai/
- Installez selon votre système d'exploitation

### 2. Installer LLaVA
```bash
# Démarrer Ollama
ollama serve

# Dans un autre terminal, installer LLaVA
ollama pull llava
```

### 3. Vérifier l'installation
```bash
python test_llava.py
```

## ⚙️ Configuration Optimale

### Script de configuration
```bash
python configure_ollama.py
```

### Configuration manuelle
Si LLaVA est trop lent, vous pouvez:
1. Utiliser un modèle plus petit: `ollama pull llava:7b`
2. Augmenter la RAM allouée à Ollama
3. Utiliser un GPU si disponible

## 🎨 Fonctionnalités avec LLaVA

### ✅ Avec LLaVA activé:
- **Analyse visuelle complète** des pages
- **Détection intelligente** des numéros manquants
- **Suggestions de position** pour les corrections
- **Analyse JSON structurée** des incohérences
- **Correction automatique** basée sur la vision

### ⚠️ Sans LLaVA (fallback):
- **Correction automatique** des patterns de numérotation
- **Détection OCR** avec Tesseract
- **Analyse de cohérence** basique
- **Toutes les fonctionnalités principales** fonctionnent

## 🔍 Exemple d'Analyse LLaVA

### Input (Image de page de catalogue):
```
Page avec 4 images d'œuvres numérotées: 1, 3, 4, 5
```

### Analyse LLaVA:
```json
{
  "numeros_visibles": [1, 2, 3, 4, 5],
  "incoherences": ["Numéro 2 manquant dans la séquence"],
  "corrections": [
    {"numero": 2, "position": "haut centre", "confiance": "haute"}
  ]
}
```

### Résultat:
- **Détection**: LLaVA voit le numéro 2 manquant
- **Position**: Indique où le trouver
- **Correction**: Le script renomme automatiquement les fichiers

## 🛠️ Dépannage

### Problème: Timeout LLaVA
```
⏰ Timeout LLaVA - le modèle est trop lent
```
**Solutions:**
1. Redémarrez Ollama: `ollama serve`
2. Utilisez un modèle plus petit: `ollama pull llava:7b`
3. Le script continuera sans LLaVA

### Problème: LLaVA ne voit pas les numéros
```
⚠️ LLaVA répond mais ne voit pas le nombre 123
```
**Solutions:**
1. Vérifiez que l'image est claire
2. Essayez un modèle plus grand: `ollama pull llava:13b`
3. Le script utilisera la correction automatique

### Problème: Ollama non accessible
```
❌ Ollama non installé ou non démarré
```
**Solutions:**
1. Installez Ollama: https://ollama.ai/
2. Démarrez Ollama: `ollama serve`
3. Le script fonctionnera sans LLaVA

## 📊 Performances

### Temps de traitement typiques:
- **Avec LLaVA**: +10-30 secondes par page
- **Sans LLaVA**: Temps normal (correction automatique)
- **Première utilisation**: LLaVA peut être plus lent (chargement du modèle)

### Optimisations:
- **GPU**: Utilisez un GPU pour accélérer LLaVA
- **RAM**: Allouez au moins 8GB à Ollama
- **Modèle**: Choisissez la taille selon vos besoins

## 🎯 Cas d'Usage

### Parfait pour:
- ✅ Catalogues d'art avec numérotation complexe
- ✅ Pages avec incohérences visuelles
- ✅ Détection de numéros manquants
- ✅ Analyse de position des œuvres

### Fonctionne aussi sans LLaVA:
- ✅ Correction automatique des patterns
- ✅ Détection OCR standard
- ✅ Renommage intelligent des fichiers
- ✅ Toutes les fonctionnalités principales

## 🔧 Scripts Utiles

- `start_extraction.py`: Démarrage automatique
- `test_llava.py`: Test des capacités LLaVA
- `configure_ollama.py`: Configuration optimale
- `extract_pdf_ultra_sensible.py`: Script principal

## 💡 Conseils

1. **Première utilisation**: Laissez LLaVA se charger complètement
2. **Performance**: Utilisez un GPU si disponible
3. **Fallback**: Le script fonctionne toujours, même sans LLaVA
4. **Debug**: Vérifiez les logs pour voir l'état de LLaVA

---

**🎨 Votre script est maintenant prêt à analyser les catalogues d'art avec l'intelligence de LLaVA !**
