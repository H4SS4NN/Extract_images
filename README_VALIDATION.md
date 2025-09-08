# 🔍 Interface de Validation PDF ULTRA

Interface web moderne pour valider et trier les images extraites par l'extracteur PDF ULTRA.

## 🚀 Démarrage Rapide

### 1. **Lancer le serveur**
```bash
# Windows
double-clic sur start_validation_server.bat

# Ou manuellement
pip install flask flask-cors
python server_validation.py
```

### 2. **Ouvrir l'interface**
- Aller sur `http://localhost:5000` dans votre navigateur
- L'interface charge automatiquement vos extractions ULTRA

### 3. **Valider les images**
- Naviguer entre les pages avec ← →
- Sélectionner les images à traiter
- Utiliser les raccourcis : **V** (valider), **R** (rejeter), **D** (douteux)
- Exporter les résultats avec le bouton 💾

## 📋 Fonctionnalités

### ✨ **Interface Moderne**
- **Design responsive** avec codes couleur clairs
- **Navigation fluide** entre les pages
- **Zoom PDF** pour examiner la page originale
- **Mode plein écran** pour les images

### 🎯 **Classification Intelligente**
- **✅ Validées** : Images confirmées comme bonnes
- **❌ Rejetées** : Faux positifs à ignorer
- **⚠️ Douteuses** : Images pré-classées par l'IA ou marquées manuellement
- **⏳ En attente** : Images pas encore traitées

### ⌨️ **Raccourcis Clavier**
- **V** : Valider la sélection
- **R** : Rejeter la sélection  
- **D** : Marquer comme douteux
- **← →** : Navigation entre pages
- **A** : Sélectionner toutes les images
- **ESC** : Annuler sélection / Fermer modale

### 📊 **Statistiques Temps Réel**
- Compteur par catégorie (validées/rejetées/douteuses/en attente)
- Barre de progression globale
- Métadonnées des images (taille, méthode détection, rotation, etc.)

## 🔧 Architecture Technique

### **Backend Flask**
- **`server_validation.py`** : Serveur principal avec API REST
- **Routes disponibles** :
  - `GET /api/get-session-data` : Données de session
  - `GET /api/get-page-images/<page>` : Images d'une page
  - `GET /api/get-image/<path>` : Servir les images
  - `POST /api/save-validation` : Sauvegarder résultats
  - `POST /api/export-validated-images` : Exporter images validées

### **Frontend HTML/JS**
- **`Interfacedecomparaison.html`** : Interface utilisateur complète
- **Intégration automatique** avec les dossiers d'extraction ULTRA
- **Mode fallback** : fonctionne même sans serveur (données de démo)

### **Intégration ULTRA**
- **Lecture automatique** des dossiers `extractions_ultra/`
- **Support dossier DOUTEUX** : affiche les images pré-classées
- **Métadonnées enrichies** : rotation, numéro d'œuvre, méthode détection
- **Fichiers d'info** : explications pour chaque image douteuse

## 📁 Structure des Fichiers

```
extractions_ultra/
├── SESSION_ULTRA_20240101_120000/
│   ├── extraction_ultra_complete.json     # Métadonnées session
│   ├── RÉSUMÉ_ULTRA.txt                   # Résumé textuel
│   ├── page_001/
│   │   ├── README_ULTRA.txt               # Détails page
│   │   ├── page_ultra_details.json        # Données techniques
│   │   ├── oeuvre_1.png                   # Images validées
│   │   ├── rectangle_02.png
│   │   ├── thumb_*.png                    # Miniatures
│   │   └── DOUTEUX/                       # Images suspectes
│   │       ├── DOUTEUX_rectangle_05.png
│   │       ├── rectangle_05_INFO.txt      # Explications
│   │       └── thumb_*.png
│   ├── page_002/
│   └── ...
└── validation_results.json                # Résultats validation
```

## 💾 Export et Sauvegarde

### **Validation Results**
- **Format JSON** avec tous les états d'images
- **Métadonnées** : session, timestamp, statistiques
- **Sauvegarde automatique** sur le serveur
- **Export local** si serveur indisponible

### **Images Validées**
- **Dossier VALIDATED_IMAGES** créé automatiquement
- **Copie physique** des images marquées comme validées
- **Nommage intelligent** : `page001_oeuvre_1.png`

## 🎨 Personnalisation

### **Modifier l'interface**
Éditer `Interfacedecomparaison.html` :
- Couleurs dans la section `<style>`
- Raccourcis dans `setupKeyboardShortcuts()`
- Métadonnées affichées dans `loadExtractedImages()`

### **Ajouter des endpoints**
Dans `server_validation.py` :
```python
@app.route('/api/mon-endpoint')
def mon_endpoint():
    return jsonify({'data': 'ma_donnée'})
```

### **Intégrer avec d'autres extracteurs**
Adapter la fonction `get_page_images()` pour lire vos formats de données.

## 🐛 Dépannage

### **Serveur ne démarre pas**
- Vérifier que Python est installé : `python --version`
- Installer les dépendances : `pip install flask flask-cors`
- Vérifier que le port 5000 n'est pas utilisé

### **Images ne s'affichent pas**
- Vérifier que le dossier `extractions_ultra/` existe
- Vérifier les permissions de fichiers
- Regarder la console du navigateur (F12) pour les erreurs

### **Pas de sessions détectées**
- Lancer d'abord l'extracteur ULTRA pour créer des sessions
- Vérifier que `extraction_ultra_complete.json` existe
- Utiliser `/api/refresh-sessions` pour rescanner

## 🔄 Workflow Complet

1. **Extraction** : Lancer `extract_pdf_ultra_sensible.py`
2. **Validation** : Démarrer `server_validation.py` 
3. **Interface** : Ouvrir `http://localhost:5000`
4. **Traitement** : Valider/rejeter les images page par page
5. **Export** : Sauvegarder les résultats et images validées
6. **Utilisation** : Images validées prêtes pour traitement final

## 📈 Statistiques

L'interface fournit des métriques détaillées :
- **Taux de validation** par page et global
- **Temps de traitement** par session
- **Répartition** des classifications (IA vs manuelle)
- **Efficacité** de l'extracteur ULTRA

---

**🎯 Résultat** : Interface complète et professionnelle pour valider efficacement vos extractions PDF ULTRA !
