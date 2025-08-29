# Meetstaat Inc. - Outil d'Analyse de Documents de Construction

Cet outil fournit une analyse avancée des documents de spécifications de construction (`cahiers des charges`) pour identifier les tâches mal placées et les problèmes d'organisation. Il utilise une combinaison de reconnaissance optique de caractères (OCR) avec LlamaParse et l'IA Gemini de Google pour une compréhension approfondie et contextuelle des documents.

## Comment ça marche

L'application suit un processus en plusieurs étapes pour analyser les documents de construction :

1.  **Traitement PDF avec LlamaParse :** Le processus commence par un document PDF, qui est traité par le pipeline LlamaParse pour extraire le texte intégral et identifier la structure du document.
2.  **Analyse par IA :** Le texte structuré est ensuite envoyé au modèle Gemini de Google, qui analyse chaque section à la recherche de tâches mal placées et de problèmes d'organisation.
3.  **Interface Utilisateur Interactive :** Les résultats sont présentés dans une interface web conviviale où vous pouvez examiner l'analyse, filtrer par catégorie de problème et obtenir un aperçu de haut niveau grâce au tableau de bord récapitulatif.

## Fonctionnalités

-   **Analyse par IA :** Utilise le modèle Gemini de Google pour analyser le texte intégral des documents de construction.
-   **Compréhension Contextuelle :** Va au-delà de la simple correspondance de mots-clés pour comprendre les relations conceptuelles entre les différentes sections.
-   **Catégorisation Nuancée des Problèmes :** Classe les problèmes en `Mauvais Placement Critique`, `Mauvaise Organisation` et `Suggestion d'Amélioration` pour une analyse plus pertinente.
-   **Interface Web Interactive :** Fournit une interface conviviale pour télécharger des documents, afficher les résultats et filtrer les problèmes.
-   **Tableau de Bord Récapitulatif :** Offre un aperçu de haut niveau des résultats de l'analyse avec des métriques clés.

## Pour commencer

### Prérequis

-   Python 3.8+
-   `pip` pour la gestion des paquets
-   Google Cloud SDK (`gcloud`) installé et authentifié

### Installation

1.  **Clonez le dépôt :**
    ```bash
    git clone <url-du-depot>
    cd Meetstaatincorp
    ```

2.  **Mettez en place un environnement virtuel :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\\Scripts\\activate`
    ```

3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Définissez les Variables d'Environnement :**
    Ce projet nécessite des clés API pour Google Cloud et LlamaParse. La manière recommandée de les définir est via des variables d'environnement.

    **Pour LlamaParse :**
    Définissez la variable d'environnement `LLAMA_CLOUD_API_KEY` avec votre clé. Pour les environnements Conda, vous pouvez la définir de manière permanente :
    ```bash
    conda env config vars set LLAMA_CLOUD_API_KEY="votre_cle_api_llama_cloud"
    ```
    Alternativement, pour le développement local, vous pouvez créer un fichier `.env` à la racine du projet et y ajouter la clé :
    ```
    LLAMA_CLOUD_API_KEY="votre_cle_api_llama_cloud"
    ```

5.  **Authentification Google Cloud :**
    Assurez-vous d'être authentifié avec la CLI `gcloud` :
    ```bash
    gcloud auth application-default login
    ```

### Lancement de l'Application

Pour démarrer le serveur web Flask, exécutez la commande suivante :
```bash
python task_placement_analyzer_app.py
```
L'application sera disponible à l'adresse `http://127.0.0.1:5002`.
