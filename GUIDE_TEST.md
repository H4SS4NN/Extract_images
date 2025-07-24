# 🧪 Guide de Test Rapide

## ✅ **Étape 1 : Vérifications**

Le serveur backend doit tourner dans une fenêtre PowerShell avec ces messages :
```
🚀 Démarrage du backend de détourage d'images
📡 API disponible sur http://localhost:5000
* Running on http://127.0.0.1:5000
* Debugger is active!
```

## 🌐 **Étape 2 : Ouvrir le Frontend**

Lancez :
```bash
python demo.py
```

Ou ouvrez directement `frontend.html` dans votre navigateur.

## 🎯 **Étape 3 : Test avec votre Image de Mains**

1. **Glissez-déposez** votre image TIFF d'études de mains
2. **Status attendu** : "Image chargée: nom_fichier.tif (X.X MB)"
3. **Ajustez la sensibilité** : 25-35 pour des dessins au crayon
4. **Cliquez** "Analyser l'image"

## 📊 **Résultats Attendus**

### ✅ **Si tout va bien :**
```
✅ 3 objets détectés (Type: Dessin)
```

- Vous devriez voir 3 cartes avec les études de mains
- Prévisualisation de chaque objet détecté
- Boutons de téléchargement PNG/JPG

### ❌ **Si problèmes :**

**"Aucun objet détecté"**
- Augmentez la sensibilité à 40-50
- Vérifiez que l'image a des contrastes nets

**"Serveur Python non disponible"**
- Vérifiez que `python backend.py` tourne
- Redémarrez le serveur si nécessaire

**"Erreur lors de l'upload"**
- Vérifiez la console du navigateur (F12)
- Regardez les logs du serveur Python

## 🔧 **Dépannage Rapide**

### **Redémarrer le système :**
```bash
# 1. Fermer le serveur (Ctrl+C)
# 2. Relancer
python backend.py

# Dans un autre terminal
python demo.py
```

### **Tester juste l'API :**
```bash
curl http://localhost:5000/health
```
Doit retourner : `{"status": "OK", "message": "Backend de détourage opérationnel"}`

### **Vérifier les dépendances :**
```bash
python -c "import cv2, numpy, flask; print('✅ Tout OK')"
```

## 🎨 **Test avec Différentes Images**

### **Dessins (sensibilité 20-40) :**
- Études de mains ✓
- Croquis architecture
- Dessins techniques

### **Photos (sensibilité 25-50) :**
- Objets sur fond uni
- Produits e-commerce

## 📱 **Interface Utilisateur**

### **Statuts possibles :**
- `Prêt - Chargez une image` : Normal
- `📁 Image chargée` : Image sélectionnée
- `🔄 Upload en cours` : Envoi au serveur
- `✅ X objets détectés` : Succès !
- `❌ Erreur: ...` : Problème à résoudre

### **Actions disponibles :**
- `💾 PNG transparent` : Fond invisible
- `💾 JPG fond blanc` : Pour impression

## 🚀 **Si tout fonctionne :**

Vous devriez pouvoir :
1. ✅ Charger votre image TIFF
2. ✅ Voir la détection automatique des 3 études de mains
3. ✅ Télécharger chaque main séparément en PNG transparent
4. ✅ Avoir des images détourées propres et nettes

## 💡 **Tips d'utilisation :**

- **Dessins fins** : Sensibilité 20-30
- **Dessins épais** : Sensibilité 30-40  
- **Photos nettes** : Sensibilité 25-35
- **Photos floues** : Sensibilité 40-60

---

**🎯 Objectif** : Vos 3 études de mains détourées automatiquement en PNG transparent !

**⏱️ Temps de traitement** : ~5-10 secondes selon la taille

**📞 Problème ?** Vérifiez les logs dans le terminal du serveur Python. 