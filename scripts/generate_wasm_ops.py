import re
import sys
import os
from pathlib import Path

def sanitize_name(name):
    return name.replace('.', '_').replace('/', '_').replace('-', '_').replace(':', '_')

def extract_index_if_exists(match_str):
    # Cerca un indice numerico dopo la virgola
    index_match = re.search(r',\s*(\d+)\s*\)', match_str)
    if index_match:
        return int(index_match.group(1))
    return None

def extract_op_names_and_modify(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        current_index = 0
        modified_lines = []
        in_define = False
        op_names = {}
        
        for line in lines:
            clean_line = line.strip()
            new_line = line
            
            # Gestisce le definizioni delle macro
            if clean_line.startswith('#'):
                original_indent = line[:len(line) - len(line.lstrip())]
                define_match = re.match(r'^\s*#\s*define\s+(\w+)', clean_line)
                
                if define_match:
                    in_define = True
                    macro_name = define_match.group(1)
                    
                    if macro_name == 'd_m3DebugOp':
                        new_line = f'{original_indent}#define d_m3DebugOp(OP, IDX) M3OP (#OP, IDX, 0, none, {{ op_##OP }})\n'
                    elif macro_name == 'd_m3DebugTypedOp':
                        if 'd_m3HasFloat' in line:
                            new_line = (f'{original_indent}#define d_m3DebugTypedOp(OP, IDX) '
                                     f'M3OP (#OP, IDX, 0, none, {{ op_##OP##_i32, op_##OP##_i64, '
                                     f'op_##OP##_f32, op_##OP##_f64, }})\n')
                        else:
                            new_line = (f'{original_indent}#define d_m3DebugTypedOp(OP, IDX) '
                                     f'M3OP (#OP, IDX, 0, none, {{ op_##OP##_i32, op_##OP##_i64 }})\n')
                
                modified_lines.append(new_line)
                continue

            if not ('M3OP' in line or 'd_m3DebugOp' in line or 'd_m3DebugTypedOp' in line):
                in_define = False
                modified_lines.append(line)
                continue

            if in_define:
                modified_lines.append(line)
                continue

            # Gestisce M3OP e M3OP_F standard
            if ('M3OP' in line or 'M3OP_F' in line) and not line.strip().startswith('#'):
                m3op_match = re.search(r'(?:M3OP|M3OP_F)\s*\(\s*"([^"]+)"', line)
                if m3op_match:
                    op_name = m3op_match.group(1)
                    op_names[op_name] = {'index': current_index, 'enum_name': sanitize_name(op_name)}
                    
                    parts = line.split(',', 2)
                    if len(parts) >= 2:
                        new_line = f"{parts[0]}, {current_index}, {parts[1].strip()}, {parts[2]}"
                        if '//' in new_line:
                            new_line = re.sub(r'//.*$', f'// 0x{current_index:02x}', new_line)
                        else:
                            new_line = f'{new_line.rstrip()}  // 0x{current_index:02x}\n'
                        current_index += 1

            # Gestisce d_m3DebugOp e d_m3DebugTypedOp
            if ('d_m3DebugOp' in line or 'd_m3DebugTypedOp' in line) and not line.strip().startswith('#'):
                new_parts = []
                last_end = 0

                # Trova tutte le occorrenze di entrambi i tipi di debug op
                debug_ops = re.finditer(r'd_m3Debug(?:Typed)?Op\s*\((\w+)(?:,\s*\d+)?\)', line)
                
                for match in debug_ops:
                    op_name = match.group(1)
                    full_match = match.group(0)
                    existing_index = extract_index_if_exists(full_match)
                    
                    # Usa l'indice esistente se presente, altrimenti usa current_index
                    index = existing_index if existing_index is not None else current_index
                    
                    # Aggiorna current_index se necessario
                    if existing_index is not None:
                        current_index = max(current_index, existing_index + 1)
                    else:
                        current_index += 1
                    
                    op_names[op_name] = {'index': index, 'enum_name': sanitize_name(op_name)}
                    
                    start = match.start()
                    new_parts.append(line[last_end:start])
                    
                    # Determina quale tipo di debug op stiamo gestendo
                    if 'TypedOp' in full_match:
                        new_parts.append(f'd_m3DebugTypedOp ({op_name}, {index})')
                    else:
                        new_parts.append(f'd_m3DebugOp ({op_name}, {index})')
                    
                    last_end = match.end()
                
                if new_parts:
                    new_parts.append(line[last_end:])
                    new_line = ''.join(new_parts)

            modified_lines.append(new_line)
            
        # Salva il file modificato
        base_name, ext = os.path.splitext(file_path)
        output_path = f"{base_name}.modified{ext}"
        with open(output_path, 'w', encoding='utf-8') as file:
            file.writelines(modified_lines)
        
        return op_names, output_path
        
    except Exception as e:
        print(f"Si è verificato un errore durante l'elaborazione del file: {str(e)}")
        return None, None

def generate_header(op_names):
    enum_text = "// Auto-generated enum for operation names\n"
    enum_text += "#pragma once\n\n"
    enum_text += "#if DEBUG && M3_FUNCTIONS_ENUM\n"
    enum_text += "enum M3OpNames {\n"
    
    added_names = []
    for name, info in sorted(op_names.items(), key=lambda x: x[1]['index']):
        enum_name = f"M3OP_NAME_{info['enum_name'].upper()}"
        if enum_name not in added_names:
            enum_text += f"    {enum_name} = {info['index']},\n"
            added_names.append(enum_name)

    
    enum_text += "};\n\n"
    
    attribute_section = '__attribute__((section(".rodata")))'
    
    array_text = "// Auto-generated array of operation names\n"
    array_text += f"static const char * const opNames[] {attribute_section} = {{\n"
    
    # Ordina per indice per mantenere l'ordine corretto
    sorted_names = sorted(op_names.items(), key=lambda x: x[1]['index'])
    for name, info in sorted_names:
        array_text += f'    "{name}",\n'
    
    array_text += "};\n\n"
    
    getter_text = "// Auto-generated getter function\n"
    getter_text += "static const char* getOpName(uint8_t id) {\n"
    getter_text += "    return opNames[id];\n"
    getter_text += "}\n"
    getter_text += "#endif\n"
    
    return enum_text + array_text + getter_text

def main():
    file_path = 'hello-idf/main/wasm3/source/operations_reference.h'

    if len(sys.argv) > 1:
        file_path = sys.argv[1]

    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    try:
        # Estrae i nomi delle operazioni e modifica il file
        op_names, modified_path = extract_op_names_and_modify(file_path)
        if not op_names:
            sys.exit(1)
            
        # Genera il file header
        output = generate_header(op_names)
        header_path = file_path.parent / "m3_op_names_generated.h"
        
        with open(header_path, 'w') as f:
            f.write(output)
            
        print(f"File modificato salvato come: {modified_path}")
        print(f"File header generato: {header_path}")
        print(f"Trovate {len(op_names)} operazioni")
        
    except Exception as e:
        print(f"Errore durante l'elaborazione: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()