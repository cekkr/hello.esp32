import re
import sys
from pathlib import Path

def sanitize_name(name):
    # Sostituisce i punti e slash con underscore
    return name.replace('.', '_').replace('/', '_')

def extract_op_names(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern modificato per catturare anche il nome dell'operazione
    pattern = r'(M3OP|M3OP_F)\s*\(\s*"([^"]+)"'
    matches = re.finditer(pattern, content)
    
    op_names = {}
    for i, match in enumerate(matches):
        op_type = match.group(1)  # M3OP o M3OP_F
        op_name = match.group(2).replace('-','_').replace('.','_').replace(':','_').replace('/','_')  # il nome dell'operazione (es: "i32.load")
        
        # Combina il tipo e il nome per l'enum
        full_name = f"{op_name}"  # oppure f"{op_type}_{op_name}" se vuoi includere il tipo
        sanitized = sanitize_name(full_name)
        op_names[full_name] = {'index': i, 'enum_name': sanitized}
    
    return op_names

def generate_header(op_names):
    enum_text = "// Auto-generated enum for operation names (by generate_c_operations_enum.py)\n"
    enum_text += "#pragma once\n"
    enum_text += "#\nif DEBUG && M3_FUNCTIONS_ENUM\n"
    enum_text += "enum M3OpNames {\n"
    
    for name, info in op_names.items():
        enum_name = f"M3OP_NAME_{info['enum_name'].upper()}"
        enum_text += f"    {enum_name} = {info['index']},\n"
    
    enum_text += "};\n\n"
    
    # or __attribute__((section(".irom.text"))) 
    # or __attribute__((section(".rodata"), aligned(4))) for alignment
    attribute_section = '__attribute__((section(".rodata")))'

    array_text = "#pragma once\n\n// Auto-generated array of operation names\n// bgenerate_c_operations_enum.py - Riccardo Cecchini \n"
    array_text += "static const char * const opNames[] "+attribute_section+" = {\n"
    
    for name in op_names.keys():
        array_text += f'    "{name}",\n'
    
    array_text += "};\n\n"
    
    getter_text = "// Auto-generated getter function\n"
    getter_text += "static const char* getOpName(uint8_t id) {\n"
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