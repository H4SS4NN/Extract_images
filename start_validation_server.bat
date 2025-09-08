@echo off
echo 🚀 Démarrage du serveur de validation PDF ULTRA
echo ================================================

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    pause
    exit /b 1
)

REM Installer Flask si nécessaire
echo 📦 Vérification des dépendances...
pip install flask flask-cors >nul 2>&1

REM Démarrer le serveur
echo 🌐 Démarrage du serveur sur http://localhost:5000
echo.
echo 💡 Conseils:
echo   - Ouvrez http://localhost:5000 dans votre navigateur
echo   - Utilisez Ctrl+C pour arrêter le serveur
echo   - L'interface se connecte automatiquement à vos extractions ULTRA
echo.
echo ================================================
python server_validation.py

pause
