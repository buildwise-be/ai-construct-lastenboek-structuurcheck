# Meetstaat Inc. - Outil d'Analyse de Documents de Construction

<p align="center">
  <img src="assets/BWlogo.png" alt="Logo de Buildwise" width="200"/>
</p>

Bienvenue dans le **Vérificateur de Structure AI-Construct**, un outil avancé conçu pour analyser l'intégrité structurelle des documents de spécifications de construction (`cahiers des charges`). Cette application web hébergée localement vous permet de télécharger n'importe quel document PDF et de recevoir une analyse approfondie, pilotée par l'IA, du placement des tâches et de l'organisation générale. L'objectif est d'identifier les incohérences, omissions et mauvais placements potentiels avant qu'ils ne deviennent des problèmes coûteux sur le chantier.

## Comment ça marche

L'application combine la puissance de l'OCR avancée avec les capacités de raisonnement des grands modèles de langage (LLM) pour offrir une expérience d'analyse fluide :

1.  **Traitement PDF avec LlamaParse :** Lorsque vous téléchargez un PDF, il est d'abord traité par LlamaParse. Ce moteur puissant extrait non seulement le texte brut, mais reconstruit également toute la structure hiérarchique du document, y compris les chapitres, sections et sous-sections.
2.  **Analyse par IA :** La sortie structurée de LlamaParse est ensuite envoyée par lots au modèle `gemini-2.5-flash` de Google. Le modèle analyse chaque section dans le contexte de l'ensemble du document pour déterminer si les tâches et les spécifications sont placées de manière logique.
3.  **Interface Utilisateur Interactive :** Les résultats de l'analyse sont présentés dans une interface web claire et interactive. Ici, vous pouvez facilement naviguer dans la structure du document, examiner les conclusions de l'IA, filtrer par catégorie de problème et obtenir un aperçu de haut niveau grâce au tableau de bord récapitulatif.

## Comment l'utiliser

L'utilisation de l'outil est conçue pour être simple et intuitive :

1.  **Démarrez l'Application :** Après avoir suivi les étapes d'installation, démarrez le serveur web local. L'outil est maintenant accessible dans votre navigateur.
2.  **Téléchargez un PDF :** L'interface offre une option claire pour sélectionner et télécharger un `cahier des charges` au format PDF depuis votre ordinateur.
3.  **Attendez le Traitement :** LlamaParse analysera votre document. La progression est visible dans l'interface, et le processus prend généralement quelques minutes, en fonction de la taille du document.
4.  **Lancez l'Analyse :** Une fois le traitement terminé, le fichier sera disponible dans un menu déroulant. Sélectionnez-le et cliquez sur "Lancer l'Analyse" pour laisser l'IA faire son travail.
5.  **Consultez les Résultats :** Les conclusions sont affichées directement sur la page. Vous pouvez parcourir les chapitres, lire les commentaires spécifiques de l'IA et évaluer la gravité des problèmes identifiés.

## Détails Techniques

Cet outil utilise des technologies de pointe pour fournir une analyse approfondie :

-   **OCR et Structuration de Document :** Nous utilisons **LlamaParse** pour la Reconnaissance Optique de Caractères (OCR) et la structuration de documents. L'OCR est le processus de conversion de texte à partir d'images ou de documents numérisés en texte lisible par machine. LlamaParse extrait non seulement le texte, mais aussi la structure hiérarchique (chapitres, sections) du document, ce qui est essentiel pour une analyse contextuelle.
-   **Analyse Structurelle :** Pour l'analyse réelle de la structure du document, nous utilisons des **appels groupés (batched) au modèle `gemini-2.5-flash` de Google**. En analysant plusieurs sections à la fois, le modèle peut mieux comprendre le contexte de l'ensemble du document et accélérer considérablement l'analyse. Un exemple du fichier JSON structuré utilisé comme entrée pour cette étape se trouve dans `examples/example_anonymized_specification.json`.
-   **Confidentialité des Données (RGPD) :** Tous les modèles d'IA sont appelés via le service **Vertex AI** de Google Cloud, qui fonctionne sur un **serveur belge (`europe-west1`)**. Cela garantit une conformité totale avec la réglementation RGPD, car vos données ne quittent pas l'UE.

## Pour commencer

### Prérequis

-   Python 3.8+
-   `pip` pour la gestion des paquets
-   Google Cloud SDK (`gcloud`) installé et authentifié. Vous devez être connecté via `gcloud auth application-default login`.

### Installation

1.  **Clonez le dépôt :**
    ```bash
    git clone <repository-url>
    cd Meetstaatincorp
    ```

2.  **Configurez un environnement virtuel :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\\Scripts\\activate`
    ```

3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Définissez les Variables d'Environnement :**
    Ce projet nécessite des clés API pour Google Cloud et LlamaParse. La manière recommandée de les définir est via les variables d'environnement.

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

## Capture d'écran

![Capture d'écran de l'outil](assets/Screenshot%202025-08-29%_20172735.png)
