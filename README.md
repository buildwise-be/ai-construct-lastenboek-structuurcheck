# Meetstaat Inc. - Analyse-instrument voor Bouwdocumenten

Dit instrument biedt een geavanceerde analyse van bouwspecificaties (Lastenboeken) om verkeerd geplaatste taken en organisationele problemen te identificeren. Het maakt gebruik van een combinatie van Optical Character Recognition (OCR) en Google's Gemini AI voor een diepgaand, contextueel begrip van de documenten.

[English](README.en.md) | [Français](README.fr.md)

## Hoe het werkt

De applicatie volgt een proces in meerdere stappen om bouwdocumenten te analyseren:

1.  **OCR-verwerking:** Het proces begint met een PDF-document, dat door een OCR-pijplijn wordt gehaald om de volledige tekst te extraheren en de inhoudsopgave te identificeren.
2.  **AI-analyse:** De volledige tekst wordt vervolgens geanalyseerd door een Generative Language Model (Google Gemini 1.5 Flash). In tegenstelling tot traditionele methoden, die afhankelijk zijn van trefwoorden, begrijpt dit model de context en de conceptuele relaties tussen verschillende secties.
3.  **Resultaten-UI:** De resultaten worden gepresenteerd in een gebruiksvriendelijke webinterface, waar u problemen kunt filteren op basis van hun categorie en de details van elk probleem kunt bekijken.

## Functies

-   **AI-gestuurde analyse:** Maakt gebruik van Google's Gemini 1.5 Flash-model om de volledige tekst van bouwdocumenten te analyseren.
-   **Contextueel begrip:** Gaat verder dan eenvoudige trefwoord-matching om de conceptuele relaties tussen verschillende secties te begrijpen.
-   **Genuanceerde probleemcategorisering:** Classificeert problemen in Kritieke misplaatsing, Slechte organisatie en Suggestie voor verbetering voor een zinvollere analyse.
-   **Interactieve web-UI:** Biedt een gebruiksvriendelijke interface om documenten te uploaden, resultaten te bekijken en problemen te filteren.
-   **Overzichtsdashboard:** Biedt een overzicht op hoog niveau van de analyseresultaten, inclusief het totaal aantal problemen per categorie.

## Aan de slag

### Vereisten

-   Python 3.8+
-   Google Cloud SDK (met gcloud geauthenticeerd)

### Installatie

1.  **Kloon de repository:**
    `ash
    git clone https://github.com/buildwise-be/ai-construct-lastenboek-structuurcheck.git
    cd ai-construct-lastenboek-structuurcheck
    `

2.  **Creëer een virtuele omgeving en installeer de afhankelijkheden:**
    `ash
    python -m venv venv
    source venv/bin/activate  # Op Windows: venv\\Scripts\\activate
    pip install -r requirements.txt
    `

3.  **Stel uw Google Cloud-project in:**
    Zorg ervoor dat u bent ingelogd met de gcloud CLI en dat uw project is ingesteld:
    `ash
    gcloud auth application-default login
    gcloud config set project UW_PROJECT_ID
    `

### Gebruik

1.  **Start de Flask-applicatie:**
    `ash
    python task_placement_analyzer_app.py
    `
2.  **Open de webinterface:**
    Navigeer naar http://127.0.0.1:5002 in uw webbrowser.

3.  **Selecteer en analyseer:**
    -   Selecteer een beschikbaar analysebestand uit de vervolgkeuzelijst.
    -   Klik op "Start Analyse".
    -   De resultaten verschijnen hieronder zodra de analyse is voltooid.

## Bijdragen

Bijdragen zijn welkom. Voor belangrijke wijzigingen, open eerst een issue om te bespreken wat u wilt wijzigen.

## Licentie

Dit project is gelicentieerd onder de MIT-licentie. Zie het LICENSE-bestand voor meer details.