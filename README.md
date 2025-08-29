# Meetstaat Inc. - Analyse-instrument voor Bouwdocumenten

![Screenshot van de tool](Requirements/Screenshot%202025-08-29%20172735.png)

<p align="center">
  <img src="Requirements/BWlogo.png" alt="Buildwise Logo" width="200"/>
</p>

Deze tool biedt een geavanceerde analyse van bouwspecificatiedocumenten (`Lastenboeken`) om misplaatste taken en organisatorische problemen te identificeren. Het is een lokaal gehoste webapplicatie die elke PDF `lastenboek` kan verwerken en de resultaten in een interactieve interface presenteert.

## Hoe het werkt

De applicatie volgt een proces in meerdere stappen om bouwdocumenten te analyseren:

1.  **PDF-verwerking met LlamaParse:** Het proces begint met een PDF-document, dat door de LlamaParse-pijplijn wordt gehaald om de volledige tekst te extraheren en de documentstructuur te identificeren.
2.  **AI-gestuurde Analyse:** De gestructureerde tekst wordt vervolgens naar het `gemini-2.5-flash`-model van Google gestuurd, dat elke sectie analyseert op misplaatste taken en organisatorische problemen.
3.  **Interactieve UI:** De resultaten worden gepresenteerd in een gebruiksvriendelijke webinterface waar u de analyse kunt bekijken, kunt filteren op probleemcategorie en een overzicht op hoog niveau kunt krijgen via het samenvattingsdashboard.

## Hoe te Gebruiken

1.  **Start de Applicatie:** Volg de installatiestappen hieronder en start de webserver. De tool draait lokaal op uw machine.
2.  **Upload een PDF:** Open de webinterface en upload een willekeurig `lastenboek` in PDF-formaat.
3.  **Wacht op Verwerking:** De tool zal de PDF verwerken met LlamaParse. Dit kan enkele minuten duren.
4.  **Start de Analyse:** Zodra de verwerking is voltooid, verschijnt uw bestand in de lijst. Selecteer het en start de analyse.
5.  **Bekijk de Resultaten:** De resultaten worden direct in de tool weergegeven, met een overzicht van mogelijke problemen, gecategoriseerd voor duidelijkheid.

## Technische Details

Deze tool maakt gebruik van geavanceerde technologieën om een diepgaande analyse te bieden:

-   **OCR en Documentstructurering:** Wij gebruiken **LlamaParse** voor Optical Character Recognition (OCR) en het structureren van documenten. OCR is het proces waarbij tekst uit afbeeldingen of gescande documenten wordt omgezet in machineleesbare tekst. LlamaParse extraheert niet alleen de tekst, maar ook de hiërarchische structuur (hoofdstukken, secties) van het document.
-   **Structurele Analyse:** Voor de daadwerkelijke analyse van de documentstructuur maken we gebruik van gebundelde (batched) aanroepen naar het **`gemini-2.5-flash`-model** van Google. Door meerdere secties tegelijk te analyseren, kunnen we de context van het hele document beter begrijpen en de analyse versnellen. Een voorbeeld van het gestructureerde JSON-bestand dat als input voor deze stap wordt gebruikt, is te vinden in `examples/example_structured_document.json`.
-   **Data Privacy (GDPR):** Alle AI-modellen worden aangeroepen via de **Vertex AI**-service van Google Cloud, die draait op een **Belgische server (`europe-west1`)**. Dit garandeert volledige conformiteit met de GDPR-regelgeving, aangezien uw gegevens de EU niet verlaten.

## Aan de slag

### Vereisten

-   Python 3.8+
-   `pip` voor pakketbeheer
-   Google Cloud SDK (`gcloud`) geïnstalleerd en geauthenticeerd. U moet ingelogd zijn via `gcloud auth application-default login`.

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
