import re
import sys
from pathlib import Path


def sanitize_name(name):
    # Sostituisce i punti con underscore
    return name.replace('.', '_').replace('/', '_')

def extract_op_names(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    pattern = r'M3OP\(\s*"([^"]+)"'
    matches = re.finditer(pattern, content)
    
    op_names = {}
    for i, match in enumerate(matches):
        name = match.group(1)
        # Usa il nome sanitizzato per l'enum ma mantiene l'originale per l'array
        sanitized = sanitize_name(name)
        op_names[name] = {'index': i, 'enum_name': sanitized}
    
    return op_names

def generate_header(op_names):
    enum_text = "// Auto-generated enum for operation names\n"
    enum_text += "enum M3OpNames {\n"
    
    for name, info in op_names.items():
        enum_name = f"M3OP_NAME_{info['enum_name'].upper()}"
        enum_text += f"    {enum_name} = {info['index']},\n"
    
    enum_text += "};\n\n"
    
    array_text = "// Auto-generated array of operation names\n"
    array_text += "static const char * const RODATA_ATTR opNames[] = {\n"
    
    for name in op_names.keys():
        array_text += f'    "{name}",\n'
    
    array_text += "};\n\n"
    
    getter_text = "// Auto-generated getter function\n"
    getter_text += "#ifdef DEBUG\n"
    getter_text += "const char* getOpName(uint8_t id) {\n"
    getter_text += "    return opNames[id];\n"
    getter_text += "}\n"
    getter_text += "#endif\n"
    
    return enum_text + array_text + getter_text


def main():

    file_path = 'hello-idf/main/wasm3/source/m3_compile.c'

    if len(sys.argv) > 1:
        file_path = sys.argv[1]

    file_path = Path(file_path)
        
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    try:
        op_names = extract_op_names(file_path)
        output = generate_header(op_names)
        
        # Scrive il risultato in un file header
        output_path = file_path.parent / "m3_op_names_generated.h"
        with open(output_path, 'w') as f:
            f.write(output)
            
        print(f"Generated header file: {output_path}")
        print(f"Found {len(op_names)} operation names")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()