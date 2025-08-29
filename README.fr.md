# Meetstaat Inc. - Outil d'Analyse de Documents de Construction

![Capture d'écran de l'outil](Requirements/Screenshot%202025-08-29%20172735.png)

<p align="center">
  <img src="Requirements/BWlogo.png" alt="Logo de Buildwise" width="200"/>
</p>

Cet outil fournit une analyse avancée des documents de spécifications de construction (`cahiers des charges`) pour identifier les tâches mal placées et les problèmes d'organisation. C'est une application web hébergée localement qui peut traiter n'importe quel `cahier des charges` au format PDF et présenter les résultats dans une interface interactive.

## Comment ça marche

L'application suit un processus en plusieurs étapes pour analyser les documents de construction :

1.  **Traitement PDF avec LlamaParse :** Le processus commence par un document PDF, qui est traité par le pipeline LlamaParse pour extraire le texte intégral et identifier la structure du document.
2.  **Analyse par IA :** Le texte structuré est ensuite envoyé au modèle `gemini-2.5-flash` de Google, qui analyse chaque section à la recherche de tâches mal placées et de problèmes d'organisation.
3.  **Interface Utilisateur Interactive :** Les résultats sont présentés dans une interface web conviviale où vous pouvez examiner l'analyse, filtrer par catégorie de problème et obtenir un aperçu de haut niveau grâce au tableau de bord récapitulatif.

## Comment l'utiliser

1.  **Démarrez l'Application :** Suivez les étapes d'installation ci-dessous et démarrez le serveur web. L'outil fonctionne localement sur votre machine.
2.  **Téléchargez un PDF :** Ouvrez l'interface web et téléchargez n'importe quel `cahier des charges` au format PDF.
3.  **Attendez le Traitement :** L'outil traitera le PDF avec LlamaParse. Cela peut prendre quelques minutes.
4.  **Lancez l'Analyse :** Une fois le traitement terminé, votre fichier apparaîtra dans la liste. Sélectionnez-le et lancez l'analyse.
5.  **Consultez les Résultats :** Les résultats sont affichés directement dans l'outil, avec un aperçu des problèmes potentiels, classés par catégorie pour plus de clarté.

## Détails Techniques

Cet outil utilise des technologies de pointe pour fournir une analyse approfondie :

-   **OCR et Structuration de Document :** Nous utilisons **LlamaParse** pour la Reconnaissance Optique de Caractères (OCR) et la structuration de documents. L'OCR est le processus de conversion de texte à partir d'images ou de documents numérisés en texte lisible par machine. LlamaParse extrait non seulement le texte, mais aussi la structure hiérarchique (chapitres, sections) du document.
-   **Analyse Structurelle :** Pour l'analyse réelle de la structure du document, nous utilisons des **appels groupés (batched) au modèle `gemini-2.5-flash` de Google**. En analysant plusieurs sections à la fois, nous pouvons mieux comprendre le contexte de l'ensemble du document et accélérer l'analyse. Un exemple du fichier JSON structuré utilisé comme entrée pour cette étape se trouve dans `examples/example_structured_document.json`.
-   **Confidentialité des Données (RGPD) :** Tous les modèles d'IA sont appelés via le service **Vertex AI** de Google Cloud, qui fonctionne sur un **serveur belge (`europe-west1`)**. Cela garantit une conformité totale avec la réglementation RGPD, car vos données ne quittent pas l'UE.

## Pour commencer

### Prérequis

-   Python 3.8+
-   `pip` pour la gestion des paquets
-   Google Cloud SDK (`gcloud`) installé et authentifié. Vous devez être connecté via `gcloud auth application-default login`.
