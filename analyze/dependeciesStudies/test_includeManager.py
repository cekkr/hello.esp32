from includeManager import *
from geminiApi import *
import json
from optimizeIncludesFuncs import *

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

    project_paths = "../../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3"
    project_paths = os.path.abspath(project_paths)

    # Uso del resolver
    if True:
        resolver = IncludeResolver(project_paths, askAI)

        print("resolver.verify_and_resolve()")
        result = resolver.verify_and_resolve()

        # Stampa risultati
        print("Analisi delle inclusioni:")
        print("\nProblemi rilevati:")
        print(custom_json_serializer(result['verification']))

        print("\nSuggerimenti AI:")
        print(custom_json_serializer(result['fixes']))

        print("\nOrdine include suggerito:")
        print(custom_json_serializer(result['include_orders']))
    else:
        analyzer = SourceAnalyzer([project_paths])
        analyzer.analyze()
        result = optimize_includes(analyzer.files)

    # Salva l'oggetto come JSON nel file "result.json"
    saveTo = "result_includeManager.json"
    print("Saving result in: ", saveTo)
    with open(saveTo, "w") as file:
        file.write(custom_json_serializer(result))
        #json.dump(result, file, indent=4)

if __name__ == "__main__":
    main()