#!/usr/bin/env python3
"""
Script de configuration pour Mistral
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from analyzers.summary_analyzer import SummaryAnalyzer

def setup_mistral():
    """Configure Mistral local pour l'analyse des sommaires"""
    print("🔧 CONFIGURATION MISTRAL LOCAL POUR ANALYSE DE SOMMAIRES")
    print("=" * 60)
    
    # Vérifier si Ollama est installé
    print("🔍 Vérification d'Ollama...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama est en cours d'exécution")
        else:
            print("❌ Ollama n'est pas en cours d'exécution")
            print("💡 Pour démarrer Ollama: ollama serve")
            return False
    except:
        print("❌ Ollama n'est pas installé ou n'est pas en cours d'exécution")
        print("\n📋 Pour installer Ollama:")
        print("   1. Allez sur https://ollama.ai/")
        print("   2. Téléchargez et installez Ollama")
        print("   3. Démarrez Ollama: ollama serve")
        return False
    
    # Tester la connexion
    print("\n🔍 Test de connexion Mistral local...")
    analyzer = SummaryAnalyzer()
    
    if analyzer.mistral_enabled:
        print("✅ Mistral local opérationnel!")
        print(f"   Modèle: {analyzer.mistral_model}")
        print("   Fonctionnalités: Analyse de sommaires, extraction d'informations d'œuvres")
    else:
        print("⚠️ Mistral non disponible - mode fallback activé")
        print("   Fonctionnalités: Extraction basique avec regex")
        print("\n💡 Pour installer Mistral:")
        print("   ollama pull mistral")
        print("   ou")
        print("   ollama pull mistral:7b")
    
    print("\n📋 Fonctionnalités disponibles:")
    print("   • Détection automatique des sommaires")
    print("   • Extraction des numéros d'œuvres")
    print("   • Analyse des informations d'œuvres (artiste, titre, dimensions, etc.)")
    print("   • Génération de JSON structuré")
    print("   • Sauvegarde des analyses")
    
    print("\n🚀 Pour utiliser l'analyseur de sommaires:")
    print("   1. Lancez l'extraction PDF normalement")
    print("   2. L'analyseur détectera automatiquement les sommaires")
    print("   3. Les analyses seront sauvegardées dans chaque page")
    print("   4. Les œuvres individuelles seront dans le dossier 'artworks'")
    
    return analyzer.mistral_enabled

if __name__ == "__main__":
    setup_mistral()
