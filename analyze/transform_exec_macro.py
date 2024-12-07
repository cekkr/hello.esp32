import re

def transform_macro(macro_text):
    # Pattern per identificare le macro d_m3Op
    macro_pattern = r'd_m3Op\s*\((.*?)\)\s*\{(.*?)\}(?=\s*\\|$)'
    
    def process_branch(code):
        # Aggiungi return prima di nextOp() e d_outOfBounds se non presente
        code = re.sub(r'(?<!return\s)(nextOp\s*\(\))', r'return \1', code)
        code = re.sub(r'(?<!return\s)(d_outOfBounds)', r'return \1', code)
        return code
    
    def transform_macro_content(match):
        macro_name = match.group(1)
        content = match.group(2)
        
        # Processa il contenuto della macro
        transformed_content = process_branch(content)
        
        # Ricostruisci la macro
        return f'd_m3Op({macro_name}){{{transformed_content}}}\\'
    
    # Applica la trasformazione
    return re.sub(macro_pattern, transform_macro_content, macro_text, flags=re.DOTALL)

def process_file(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read()
        
        # Trasforma il contenuto
        transformed = transform_macro(content)
        
        # Scrivi il risultato
        with open(output_file, 'w') as f:
            f.write(transformed)
            
        print(f"Trasformazione completata. Output salvato in: {output_file}")
        
    except Exception as e:
        print(f"Errore durante la processazione del file: {str(e)}")

if __name__ == "__main__":
    input_path = "../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/m3_exec.h"
    output_path = "m3_exec_transformed.h"
    process_file(input_path, output_path)