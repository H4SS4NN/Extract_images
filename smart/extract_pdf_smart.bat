@echo off
chcp 65001 > nul
title Extracteur PDF SMART QUALITY

echo.
echo 🚀 EXTRACTEUR PDF SMART QUALITY
echo ================================
echo.
echo 🎯 MODE SMART - Qualité + OCR intelligent !
echo.
echo ✨ NOUVELLES FONCTIONNALITÉS SMART:
echo   📊 Vérification automatique de qualité (seuil 50%%)
echo   🔍 OCR par tâtonnement (5px, 10px, 15px, 20px, 30px, 50px)
echo   🎯 4 hauteurs de zone testées par distance
echo   🧠 Classification automatique par qualité
echo   🗂️ Dossiers séparés: qualite_OK / qualite_DOUTEUSE
echo   ⚡ Préfixe DOUTEUX_ pour images de mauvaise qualité
echo   🔬 Évaluation multi-critères (netteté, contraste, taille)
echo   🔄 CORRECTION AUTOMATIQUE DE ROTATION (nouveau !)
echo.
echo 🎨 POUR PICASSO: Devrait capturer ET bien classer les images !
echo.

py -3 extract_pdf_smart_quality.py

echo.
echo 📋 Appuyez sur une touche pour fermer...
pause > nul
