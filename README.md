# Meetstaat Inc. - Analyse-instrument voor Bouwdocumenten

Deze tool biedt een geavanceerde analyse van bouwspecificatiedocumenten (`Lastenboeken`) om misplaatste taken en organisatorische problemen te identificeren. Het maakt gebruik van een combinatie van Optical Character Recognition (OCR) met LlamaParse en de Gemini AI van Google voor een diepgaand, contextueel begrip van de documenten.

## Hoe het werkt

De applicatie volgt een proces in meerdere stappen om bouwdocumenten te analyseren:

1.  **PDF-verwerking met LlamaParse:** Het proces begint met een PDF-document, dat door de LlamaParse-pijplijn wordt gehaald om de volledige tekst te extraheren en de documentstructuur te identificeren.
2.  **AI-gestuurde Analyse:** De gestructureerde tekst wordt vervolgens naar het Gemini-model van Google gestuurd, dat elke sectie analyseert op misplaatste taken en organisatorische problemen.
3.  **Interactieve UI:** De resultaten worden gepresenteerd in een gebruiksvriendelijke webinterface waar u de analyse kunt bekijken, kunt filteren op probleemcategorie en een overzicht op hoog niveau kunt krijgen via het samenvattingsdashboard.

## Functies

-   **AI-gestuurde Analyse:** Maakt gebruik van het Gemini-model van Google om de volledige tekst van bouwdocumenten te analyseren.
-   **Contextueel Begrip:** Gaat verder dan eenvoudige trefwoordmatching om de conceptuele relaties tussen verschillende secties te begrijpen.
-   **Genuanceerde Probleemcategorisering:** Classificeert problemen in `Kritieke Misplaatsing`, `Slechte Organisatie` en `Suggestie voor Verbetering` voor een zinvollere analyse.
-   **Interactieve Web-UI:** Biedt een gebruiksvriendelijke interface om documenten te uploaden, resultaten te bekijken en problemen te filteren.
-   **Samenvattend Dashboard:** Biedt een overzicht op hoog niveau van de analyseresultaten met belangrijke statistieken.

## Aan de slag

### Vereisten

-   Python 3.8+
-   `pip` voor pakketbeheer
-   Google Cloud SDK (`gcloud`) geïnstalleerd en geauthenticeerd

### Installatie

1.  **Kloon de repository:**
    ```bash
    git clone <repository-url>
    cd Meetstaatincorp
    ```

2.  **Stel een virtuele omgeving in:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Gebruik op Windows `venv\\Scripts\\activate`
    ```

3.  **Installeer de afhankelijkheden:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Stel Omgevingsvariabelen in:**
    Dit project vereist API-sleutels voor Google Cloud en LlamaParse. De aanbevolen manier om deze in te stellen is via omgevingsvariabelen.

    **Voor LlamaParse:**
    Stel de `LLAMA_CLOUD_API_KEY` omgevingsvariabele in op uw sleutel. Voor Conda-omgevingen kunt u dit permanent instellen:
    ```bash
    conda env config vars set LLAMA_CLOUD_API_KEY="uw_llama_cloud_api_sleutel"
    ```
    Als alternatief kunt u voor lokale ontwikkeling een `.env`-bestand in de hoofdmap van het project aanmaken en de sleutel daar toevoegen:
    ```
    LLAMA_CLOUD_API_KEY="uw_llama_cloud_api_sleutel"
    ```

5.  **Google Cloud Authenticatie:**
    Zorg ervoor dat u bent geauthenticeerd met de `gcloud` CLI:
    ```bash
    gcloud auth application-default login
    ```

### De Applicatie Draaien

Om de Flask-webserver te starten, voert u het volgende commando uit:
```bash
python task_placement_analyzer_app.py
```
De applicatie zal beschikbaar zijn op `http://127.0.0.1:5002`.
