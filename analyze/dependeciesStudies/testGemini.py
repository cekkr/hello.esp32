from geminiApi import *

def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

def main():
    # Inizializzazione del client
    client = GeminiClient(api_key=load_gemini_key("../geminiConfig.env"))

    # Generazione di testo semplice
    if False:
        response = client.generate_text(
            prompt="Scrivi una poesia sulla primavera",
            temperature=0.8
        )
        print(response)

    # Generazione con istruzioni di sistema
    if False:
        response = client.generate_text(
            prompt="Analizza questo testo",
            system_instructions="Sei un esperto di analisi letteraria"
        )
        print(response)
    
    # Output strutturato in JSON
    if True:
        response = client.generate_text(
            system_instructions="Scomponi questo testo in una struttura di analisi grammaticale e logica",
            prompt="La mia gatta si chiama Neve perchè è bianca",
            structured_output={
                "type": "object",
                "properties": {
                    "sentiment": {"type": "string"},
                    "score": {"type": "number"}
                }
            }
        )
        print(response)

    # Statistiche della cache
    stats = client.get_cache_stats()
    print(f"Totale entry in cache: {stats['total_entries']}")

if __name__ == "__main__":
    main()