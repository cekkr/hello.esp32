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
    response = client.generate_text(
        prompt="Scrivi una poesia sulla primavera",
        temperature=0.8
    )

    # Generazione con istruzioni di sistema
    response = client.generate_text(
        prompt="Analizza questo testo",
        system_instructions="Sei un esperto di analisi letteraria"
    )

    # Output strutturato in JSON
    response = client.generate_text(
        prompt="Analizza il sentiment di questo testo",
        structured_output={
            "type": "object",
            "properties": {
                "sentiment": {"type": "string"},
                "score": {"type": "number"}
            }
        }
    )

    # Statistiche della cache
    stats = client.get_cache_stats()
    print(f"Totale entry in cache: {stats['total_entries']}")

if __name__ == "__main__":
    main()