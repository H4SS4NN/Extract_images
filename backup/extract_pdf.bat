@echo off
chcp 65001 > nul
title Extracteur PDF - Mode Script

echo.
echo 🚀 EXTRACTEUR PDF - MODE SCRIPT DIRECT
echo =======================================
echo.
echo ✨ FONCTIONNALITÉS:
echo   📁 Organisation par page (dossier page_XXX)
echo   📝 Fichier README.txt par page avec détails
echo   🖼️  Extraction automatique des images
echo   🎯 Auto-détection intelligente
echo   🏷️  Détection numéros d'œuvre (OCR)
echo   📊 Logs JSON complets
echo   🖼️  Miniatures automatiques
echo.

py -3 extract_pdf_script.py

echo.
echo 📋 Appuyez sur une touche pour fermer...
pause > nul
