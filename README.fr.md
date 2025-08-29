# Meetstaat Inc. - Outil d'Analyse pour Documents de Construction

Cet outil fournit une analyse avancée des documents de spécifications de construction (`Cahiers des Charges`) pour identifier les tâches mal placées et les problèmes d'organisation. Il utilise une combinaison de Reconnaissance Optique de Caractères (OCR) et de l'IA Gemini de Google pour une compréhension contextuelle approfondie des documents.

[Nederlands](README.md) | [English](README.en.md)

## Comment ça fonctionne

L'application suit un processus en plusieurs étapes pour analyser les documents de construction :

1.  **Traitement OCR :** Le processus commence par un document PDF, qui est passé dans un pipeline OCR pour extraire le texte intégral et identifier la table des matières.
2.  **Analyse par IA :** Le texte intégral est ensuite analysé par un `Modèle de Langage Génératif` (Google Gemini 1.5 Flash). Contrairement aux méthodes traditionnelles basées sur des mots-clés, ce modèle comprend le contexte et les relations conceptuelles entre les différentes sections.
3.  **Interface utilisateur des résultats :** Les résultats sont présentés dans une interface web conviviale, où vous pouvez filtrer les problèmes par catégorie et consulter les détails de chaque problème.

## Fonctionnalités

-   **Analyse par IA :** Utilise le modèle Gemini 1.5 Flash de Google pour analyser le texte intégral des documents de construction.
-   **Compréhension contextuelle :** Va au-delà de la simple correspondance de mots-clés pour comprendre les relations conceptuelles entre les différentes sections.
-   **Catégorisation nuancée des problèmes :** Classe les problèmes en `Mauvais emplacement critique`, `Mauvaise organisation` et `Suggestion d'amélioration` pour une analyse plus pertinente.
-   **Interface web interactive :** Fournit une interface conviviale pour télécharger des documents, afficher les résultats et filtrer les problèmes.
-   **Tableau de bord de synthèse :** Offre un aperçu de haut niveau des résultats de l'analyse, y compris le nombre total de problèmes par catégorie.

## Pour commencer

### Prérequis

-   Python 3.8+
-   Google Cloud SDK (avec `gcloud` authentifié)

### Installation

1.  **Clonez le dépôt :**
    ```bash
    git clone https://github.com/buildwise-be/ai-construct-lastenboek-structuurcheck.git
    cd ai-construct-lastenboek-structuurcheck
    ```

2.  **Créez un environnement virtuel et installez les dépendances :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Configurez votre projet Google Cloud :**
    Assurez-vous d'être connecté avec la CLI gcloud et que votre projet est configuré :
    ```bash
    gcloud auth application-default login
    gcloud config set project VOTRE_ID_PROJET
    ```

### Utilisation

1.  **Démarrez l'application Flask :**
    ```bash
    python task_placement_analyzer_app.py
    ```
2.  **Ouvrez l'interface web :**
    Naviguez vers `http://127.0.0.1:5000` dans votre navigateur web.

3.  **Sélectionnez et analysez :**
    -   Sélectionnez un fichier d'analyse disponible dans le menu déroulant.
    -   Cliquez sur "Démarrer l'analyse".
    -   Les résultats apparaîtront ci-dessous une fois l'analyse terminée.

## Contribuer

Les contributions sont les bienvenues. Pour des changements majeurs, veuillez d'abord ouvrir une issue pour discuter de ce que vous souhaitez modifier.

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.
