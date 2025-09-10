# 📐 Détection de Rectangles avec Correction de Perspective v2.0

## 🎯 Vue d'ensemble

Système intelligent de détection et extraction de formes rectangulaires avec correction automatique de perspective. Parfait pour numériser des documents, extraire des cartes, redresser des photos, etc.

## ✨ Nouvelles fonctionnalités v2.0

### 🔄 Changement d'approche complet
- **Avant** : Détourage d'objets par segmentation
- **Maintenant** : Détection de rectangles avec correction de perspective

### 🎯 Ce que fait le système
1. **Détecte automatiquement** les formes rectangulaires dans l'image
2. **Identifie les 4 coins** de chaque rectangle avec précision
3. **Applique une correction de perspective** pour redresser
4. **Extrait l'image rectifiée** en haute qualité

### 📋 Cas d'usage parfaits
- 📄 **Documents scannés** (factures, contrats, lettres)
- 🗺️ **Cartes et plans** 
- 🖼️ **Photos de tableaux/affiches**
- 📱 **Screenshots d'écrans**
- 🎨 **Dessins géométriques**
- 📋 **Formulaires et tableaux**

## 🚀 Installation et lancement

### Démarrage rapide
```bash
python start.py
```

### Ou démarrage manuel
```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer le backend
python backend.py

# 3. Ouvrir frontend.html dans le navigateur
```

## 🎛️ Comment utiliser

### 1. Upload de l'image
- Glissez-déposez votre image sur la zone de upload
- Ou cliquez pour sélectionner un fichier
- Formats supportés : JPG, PNG, GIF, BMP, TIFF

### 2. Réglage de la sensibilité
- **Sensibilité basse (10-30)** : Détecte uniquement les rectangles très nets
- **Sensibilité moyenne (40-60)** : Équilibre optimal pour la plupart des cas
- **Sensibilité haute (70-100)** : Détecte plus de formes, risque de faux positifs

### 3. Analyse et extraction
- Cliquez sur "🔍 Détecter les rectangles"
- Visualisez les rectangles détectés avec leurs coins marqués
- Téléchargez individuellement ou en lot

## 🔧 Algorithmes utilisés

### Détection des contours
- **Seuillage adaptatif** pour améliorer le contraste
- **Détection de bords Canny** pour identifier les contours nets
- **Morphologie mathématique** pour nettoyer les contours

### Approximation polygonale
- **Douglas-Peucker** pour simplifier les contours en polygones
- **Détection de quadrilatères convexes** 
- **Fallback sur rectangle englobant** si nécessaire

### Correction de perspective
- **Calcul automatique des 4 coins** (top-left, top-right, bottom-right, bottom-left)
- **Transformation de perspective OpenCV** pour redresser
- **Calcul optimal des dimensions** de sortie

## 📊 API Endpoints

### POST `/upload`
Upload et analyse d'une image
```json
{
  "filename": "image.jpg",
  "rectangles_count": 3,
  "rectangles": [
    {
      "id": 0,
      "bbox": {"x": 100, "y": 150, "w": 400, "h": 300},
      "area": 120000,
      "corners": [[100,150], [500,150], [500,450], [100,450]],
      "is_bounding_box": false
    }
  ]
}
```

### GET `/preview/<id>`
Prévisualisation avec coins marqués

### GET `/extract/<id>`
Télécharger rectangle extrait et redressé
- Paramètre `format` : `png` ou `jpg`

### GET `/extract_all`
Télécharger tous les rectangles en ZIP

## 🎨 Améliorations visuelles

### Interface utilisateur
- 📐 **Icônes géométriques** pour refléter la nouvelle fonction
- 🎯 **Prévisualisations avec coins marqués** pour voir la détection
- ✅ **Indicateurs de qualité** (détection précise vs approximative)
- 📊 **Informations détaillées** sur chaque rectangle

### Feedback visuel
- **Contours verts** pour les rectangles détectés
- **Points rouges numérotés** pour les 4 coins
- **Indicateurs de qualité** pour chaque détection

## 🔍 Exemples d'utilisation

### Document incliné
1. Photo d'une facture prise à la va-vite ➡️ Document parfaitement droit
2. Scan mal cadré ➡️ Extraction précise du contenu

### Carte ou plan
1. Photo de carte routière ➡️ Carte redressée utilisable
2. Plan architectural incliné ➡️ Plan droit et net

### Tableau ou affiche
1. Photo de tableau en perspective ➡️ Vue frontale parfaite
2. Affiche photographiée de biais ➡️ Image droite

## ⚙️ Configuration technique

### Paramètres de détection
- **Aire minimale** : 1/50ème de l'image totale
- **Approximation polygonale** : 1-2% du périmètre
- **Filtrages morphologiques** : kernels adaptatifs
- **Limite de détection** : 10 rectangles maximum

### Qualité de sortie
- **PNG** : Compression sans perte, idéal pour documents
- **JPG** : Haute qualité (95%), plus compact pour photos

## 🎯 Avantages de cette approche

### Par rapport au détourage classique
- ✅ **Plus précis** pour les formes géométriques
- ✅ **Correction automatique** de la perspective
- ✅ **Parfait pour documents** et contenus rectangulaires
- ✅ **Résultats plus prévisibles** et utilisables

### Cas d'usage optimaux
- 📄 **Numérisation de documents**
- 🗺️ **Extraction de cartes**
- 📱 **Redressement de screenshots**
- 🖼️ **Correction de photos de tableaux**

## 🚀 Performance

- **Détection rapide** grâce aux algorithmes optimisés OpenCV
- **Correction de perspective temps réel**
- **Extraction haute qualité** sans perte
- **Interface responsive** avec feedback immédiat

---

*Développé avec OpenCV, Flask et JavaScript moderne* 