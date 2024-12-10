from includeManager import *
from geminiApi import *

client = None

def askAI(instruction, prompt):
    global client
    print("askAI request:\nInstruction:\n", instruction, "\nPrompt:\n", prompt)
    response = client.generate_text(
            system_instructions=instruction,
            prompt=prompt,
            structured_output={
                "type": "object",
                "properties": {
                    "sentiment": {"type": "string"},
                    "score": {"type": "number"}
                }
            }
        )

    print("Response: \n", response, "\n\n")
    
    return response

def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

def main():
    print("Starting IncludeManager...")

    global client    
    client = GeminiClient(api_key=load_gemini_key("../geminiConfig.env"))    
    print("GeminiClient loaded successfully")

    # Uso del resolver
    project_paths = "../../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3"
    resolver = IncludeResolver(project_paths, askAI)

    print("resolver.verify_and_resolve()")
    result = resolver.verify_and_resolve()

    # Stampa risultati
    print("Analisi delle inclusioni:")
    print("\nProblemi rilevati:")
    print(json.dumps(result['verification'], indent=2))

    print("\nSuggerimenti AI:")
    print(json.dumps(result['fixes'], indent=2))

    print("\nOrdine include suggerito:")
    print(json.dumps(result['include_orders'], indent=2))

if __name__ == "__main__":
    main()