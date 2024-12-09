from includeManager import *
from geminiApi import *

# Mock AI prompt function
def mock_ai_prompt(instruction: str, prompt: str) -> dict:
    # Simula una risposta dell'AI per testing
    return {
        "new_headers": [
            {
                "name": "common_types.h",
                "symbols": ["user_info_t", "session_data_t"],
                "reason": "Separate common type definitions to break circular dependency"
            }
        ],
        "moved_symbols": [],
        "include_order_fixes": []
    }

# Esempio di progetto
source_files = {
    Path("user.h"): SourceFile(
        path=Path("user.h"),
        includes=[Path("session.h")],
        included_by=set([Path("main.c")]),
        definitions=[
            Symbol("user_info_t", "type", 10, "struct user_info { char* name; int id; }"),
            Symbol("create_user", "function", 15, "user_info_t* create_user(const char* name)")
        ],
        usages=[
            Symbol("session_data_t", "type", 12, "session_data_t* session")
        ],
        is_header=True
    ),
    
    Path("session.h"): SourceFile(
        path=Path("session.h"),
        includes=[Path("user.h")],
        included_by=set([Path("main.c")]),
        definitions=[
            Symbol("session_data_t", "type", 5, "struct session_data { int session_id; user_info_t* user; }"),
            Symbol("create_session", "function", 10, "session_data_t* create_session(user_info_t* user)")
        ],
        usages=[
            Symbol("user_info_t", "type", 5, "user_info_t* user")
        ],
        is_header=True
    ),
    
    Path("main.c"): SourceFile(
        path=Path("main.c"),
        includes=[Path("user.h"), Path("session.h")],
        included_by=set(),
        definitions=[
            Symbol("main", "function", 1, "int main(void)")
        ],
        usages=[
            Symbol("user_info_t", "type", 4, "user_info_t* user"),
            Symbol("session_data_t", "type", 5, "session_data_t* session"),
            Symbol("create_user", "function", 6, "user = create_user(\"test\")"),
            Symbol("create_session", "function", 7, "session = create_session(user)")
        ],
        is_header=False
    )
}

client = None

def askAI(instruction, prompt):
    global client

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
    
    return response

def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

def main():
    global client
    client = GeminiClient(api_key=load_gemini_key("../geminiConfig.env"))    

    # Uso del resolver
    project_paths = "../../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3"
    resolver = IncludeResolver(project_paths, askAI)
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