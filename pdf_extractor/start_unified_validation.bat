@echo off
echo 🚀 PROFESSIONAL ART VALIDATION INTERFACE
echo ================================================
echo 🎭 Picasso + 🎨 Dubuffet - Unified Professional Interface
echo ================================================

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    pause
    exit /b 1
)

REM Installer Flask si nécessaire
echo 📦 Installing dependencies...
pip install flask flask-cors pdf2image >nul 2>&1

REM Démarrer le serveur unifié
echo 🌐 Starting professional validation server on http://localhost:5000
echo.
echo ✨ FEATURES:
echo   🎭 PICASSO : Classic validation interface
echo   🎨 DUBUFFET : Advanced OCR + Individual JSONs + Debug images
echo   🔄 Dynamic session switching
echo   🔧 Page offset correction (automatic)
echo   📱 Professional responsive design
echo   🎨 Modern UI with Lucide icons
echo   📊 Real-time validation statistics
echo.
echo 💡 USAGE:
echo   - Open http://localhost:5000 in your browser
echo   - Use session selector to switch between collections
echo   - Interface adapts automatically (Picasso/Dubuffet)
echo   - PDF pages and images are now perfectly synchronized
echo   - Professional design with real icons and modern colors
echo   - Use Ctrl+C to stop the server
echo.
echo ================================================
python unified_validation_server.py

pause
