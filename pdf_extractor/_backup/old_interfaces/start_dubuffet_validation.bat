@echo off
echo 🎨 Démarrage du serveur de validation DUBUFFET avec OCR
echo =========================================================

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    pause
    exit /b 1
)

REM Installer Flask si nécessaire
echo 📦 Vérification des dépendances...
pip install flask flask-cors pdf2image >nul 2>&1

REM Démarrer le serveur Dubuffet
echo 🌐 Démarrage du serveur Dubuffet sur http://localhost:5001
echo.
echo 🎨 Fonctionnalités Dubuffet:
echo   - Visualisation des résultats OCR pour chaque image
echo   - Affichage des légendes extraites (titre, médium, dimensions, date)
echo   - JSON individuels d'œuvres au format Picasso
echo   - Images debug OCR (zones analysées + texte brut)
echo   - Validation interactive avec données OCR
echo.
echo 💡 Conseils:
echo   - Ouvrez http://localhost:5001 dans votre navigateur
echo   - L'interface détecte automatiquement les sessions Dubuffet
echo   - Cliquez sur les images pour voir les détails OCR
echo   - Les JSON d'œuvres sont accessibles depuis l'interface
echo   - Utilisez Ctrl+C pour arrêter le serveur
echo.
echo =========================================================
python dubuffet_validation_server.py

pause
