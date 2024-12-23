#!/usr/bin/env python3
import re
import sys
import os


def extract_function_info(header_content):
    """Estrae sia le dichiarazioni che le definizioni complete di funzione dal file header."""
    functions = []
    current_function = []
    in_function = False
    brace_count = 0

    lines = header_content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Se non siamo in una funzione, cerca una nuova dichiarazione/definizione
        if not in_function:
            # Pattern per l'inizio di una funzione (tipo ritorno, nome, parametri)
            match = re.match(r'^(\s*)([\w\*]+\s+[\w\*]+\s*\([^)]*\))\s*({)?', line)
            if match:
                indentation = match.group(1)  # Preserva l'indentazione originale
                signature = match.group(2)
                has_body = match.group(3) is not None

                if has_body:
                    # Inizia una nuova funzione con implementazione
                    in_function = True
                    brace_count = 1
                    current_function = [line]  # Mantiene la riga originale completa
                else:
                    # È solo una dichiarazione
                    if line.strip().endswith(';'):
                        functions.append((signature, None))
                    else:
                        # La funzione inizia nella prossima riga
                        current_function = [line]
                        in_function = True
        else:
            # Siamo dentro una funzione, raccogli il corpo mantenendo l'indentazione
            current_function.append(line)

            # Conta le parentesi graffe
            brace_count += line.count('{') - line.count('}')

            # Se abbiamo chiuso tutte le parentesi graffe, la funzione è completa
            if brace_count == 0:
                in_function = False
                full_implementation = '\n'.join(current_function)
                # Estrai la signature dalla prima riga
                match = re.match(r'\s*([\w\*]+\s+[\w\*]+\s*\([^)]*\))', current_function[0])
                if match:
                    signature = match.group(1)
                    functions.append((signature, full_implementation))
                current_function = []

        i += 1

    # Separa dichiarazioni e implementazioni
    declarations = [f"{signature};" for signature, _ in functions]
    implementations = [impl if impl else f"{signature} {{\n    // TODO: Implementa questa funzione\n}}"
                       for signature, impl in functions]

    return declarations, implementations


def extract_includes_and_guards(header_content):
    """Estrae include e guardie dell'header."""
    includes = []
    guards = []

    lines = header_content.split('\n')
    for line in lines:
        if '#include' in line:
            includes.append(line)
        elif any(guard in line for guard in ['#ifndef', '#define', '#endif']):
            guards.append(line)

    return includes, guards


def extract_typedefs_and_structs(header_content):
    """Estrae typedef e struct dal header."""
    # Pattern per trovare struct e typedef completi
    struct_pattern = r'(typedef\s+struct\s+\w*\s*{[^}]*}\s*\w*\s*;)'
    typedef_pattern = r'(typedef\s+[\w\s\*]+;)'

    # Trova tutte le corrispondenze
    structs = re.findall(struct_pattern, header_content, re.DOTALL)
    typedefs = re.findall(typedef_pattern, header_content)

    return structs + typedefs


def generate_source_file(header_path, implementations, includes):
    """Genera il file sorgente .c corrispondente."""
    header_name = os.path.basename(header_path)
    source_content = []

    # Aggiungi gli include necessari
    source_content.extend(includes)
    # Aggiungi l'include del proprio header
    source_content.append(f'#include "{header_name}"')
    source_content.append('')  # Linea vuota per separazione

    # Aggiungi le implementazioni delle funzioni
    for impl in implementations:
        if impl:
            # Rimuovi l'eventuale ripetizione dell'header della funzione se presente
            impl_lines = impl.split('\n')
            if len(impl_lines) > 1 and re.match(r'\s*[\w\*]+\s+[\w\*]+\s*\([^)]*\)\s*{', impl_lines[1]):
                source_content.append('\n'.join(impl_lines[1:]))
            else:
                source_content.append(impl)
            source_content.append('')  # Linea vuota tra le funzioni

    return '\n'.join(source_content)


def update_header_file(header_content, declarations, includes, guards, types):
    """Aggiorna il file header mantenendo solo le dichiarazioni."""
    new_header = []

    # Aggiungi le guardie di apertura
    if guards and '#ifndef' in guards[0]:
        new_header.extend(guards[:2])

    # Aggiungi gli include
    new_header.extend(includes)
    new_header.append('')  # Linea vuota per separazione

    # Aggiungi i typedef e struct
    new_header.extend(types)
    if types:
        new_header.append('')  # Linea vuota per separazione

    # Aggiungi le dichiarazioni di funzione
    new_header.extend(declarations)

    # Aggiungi la guardia di chiusura
    if guards and '#endif' in guards[-1]:
        new_header.append(guards[-1])

    return '\n'.join(new_header)


def process_header_file(header_path):
    """Processa il file header e genera il corrispondente file sorgente."""
    try:
        # Leggi il contenuto del file header
        with open(header_path, 'r') as f:
            header_content = f.read()

        # Estrai le varie parti
        declarations, implementations = extract_function_info(header_content)
        includes, guards = extract_includes_and_guards(header_content)
        types = extract_typedefs_and_structs(header_content)

        # Genera il nuovo contenuto del header
        new_header_content = update_header_file(
            header_content, declarations, includes, guards, types
        )

        # Genera il contenuto del file sorgente
        source_content = generate_source_file(
            header_path, implementations, includes
        )

        # Scrivi i file
        source_path = header_path.replace('.h', '.c')

        with open(header_path, 'w') as f:
            f.write(new_header_content)

        with open(source_path, 'w') as f:
            f.write(source_content)

        print(f"File header aggiornato: {header_path}")
        print(f"File sorgente generato: {source_path}")

    except Exception as e:
        print(f"Errore durante l'elaborazione: {str(e)}")
        sys.exit(1)

def main():
    header_file = '../' + 'hello-idf/main/he_io.h'

    if len(sys.argv) > 1:
        header_file = sys.argv[1]

    if not header_file.endswith('.h'):
        print("Il file deve essere un header file .h")
        sys.exit(1)

    process_header_file(header_file)


if __name__ == "__main__":
    main()