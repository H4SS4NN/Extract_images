#!/usr/bin/env python3
"""
Démonstration de l'analyseur de sommaires
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from analyzers.summary_analyzer import SummaryAnalyzer
import json

def demo_summary_analyzer():
    """Démonstration de l'analyseur de sommaires"""
    print("🔍 DÉMONSTRATION ANALYSEUR DE SOMMAIRES")
    print("=" * 50)
    
    # Créer l'analyseur (Mistral local via Ollama)
    analyzer = SummaryAnalyzer()
    
    # Texte d'exemple de sommaire
    sample_text = """
    SOMMAIRE
    
    1. Pablo Picasso, Les Demoiselles d'Avignon, 1907, huile sur toile, 243.9 x 233.7 cm, signé
    2. Pablo Picasso, Guernica, 1937, huile sur toile, 349.3 x 776.6 cm, signé
    3. Pablo Picasso, La Vie, 1903, huile sur toile, 196.5 x 128.9 cm, signé
    4. Pablo Picasso, Les Saltimbanques, 1905, huile sur toile, 212.8 x 229.6 cm, signé
    5. Pablo Picasso, Portrait de Dora Maar, 1937, huile sur toile, 92 x 65 cm, signé
    """
    
    print("📋 Texte d'exemple:")
    print(sample_text)
    print("\n" + "=" * 50)
    
    # Détecter si c'est un sommaire
    is_summary = analyzer.detect_summary_page(sample_text)
    print(f"🔍 Détection sommaire: {'✅ Oui' if is_summary else '❌ Non'}")
    
    if is_summary:
        # Extraire les entrées
        entries = analyzer.extract_artwork_entries(sample_text)
        print(f"📋 Entrées trouvées: {len(entries)}")
        
        for entry in entries:
            print(f"  • Numéro {entry['artwork_number']}: {entry['raw_text']}")
        
        print("\n" + "=" * 50)
        
        # Analyser chaque entrée (sans IA pour la démo)
        print("🔍 Analyse des entrées (mode fallback):")
        for entry in entries:
            print(f"\n📝 Entrée {entry['artwork_number']}:")
            analyzed = analyzer.analyze_artwork_entry(entry)
            
            print(f"  Artiste: {analyzed.get('artist_name', 'N/A')}")
            print(f"  Titre: {analyzed.get('title', 'N/A')}")
            print(f"  Dimensions: {analyzed.get('size', 'N/A')} {analyzed.get('size_unit', '')}")
            print(f"  Année: {analyzed.get('execution_year', 'N/A')}")
            print(f"  Signature: {'Oui' if analyzed.get('signature') else 'Non'}")
            print(f"  Confiance: {analyzed.get('confidence', 0):.2f}")
            
            # Créer le JSON structuré
            artwork_json = analyzer.create_artwork_json(analyzed)
            print(f"  JSON généré: {len(artwork_json)} caractères")
    
    print("\n" + "=" * 50)
    print("✅ Démonstration terminée!")
    print("\n💡 Pour utiliser Mistral local:")
    print("   1. Installez Ollama: https://ollama.ai/")
    print("   2. Installez Mistral: ollama pull mistral")
    print("   3. Démarrez Ollama: ollama serve")
    print("   4. Relancez le script")

if __name__ == "__main__":
    demo_summary_analyzer()
