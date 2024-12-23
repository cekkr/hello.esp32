#!/usr/bin/env python3
import re
import sys
import os


def extract_function_declarations(header_content):
    """Estrae le dichiarazioni di funzione dal file header."""
    # Pattern per trovare le dichiarazioni di funzione
    # Cattura: tipo di ritorno, nome funzione, parametri
    pattern = r'^\s*([\w\*]+\s+[\w\*]+\s*\([^)]*\))\s*;'

    declarations = []
    implementations = []

    for line in header_content.split('\n'):
        match = re.match(pattern, line)
        if match:
            # Ottiene la dichiarazione completa
            declaration = match.group(1)
            declarations.append(declaration + ';')
            # Crea l'implementazione base
            implementations.append(f"{declaration} {{\n    // TODO: Implementa questa funzione\n}}\n")

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


def generate_source_file(header_path, declarations, implementations, includes):
    """Genera il file sorgente .c corrispondente."""
    header_name = os.path.basename(header_path)
    source_content = []

    # Aggiungi gli include necessari
    source_content.extend(includes)
    # Aggiungi l'include del proprio header
    source_content.append(f'#include "{header_name}"')
    source_content.append('')  # Linea vuota per separazione

    # Aggiungi le implementazioni delle funzioni
    source_content.extend(implementations)

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
        declarations, implementations = extract_function_declarations(header_content)
        includes, guards = extract_includes_and_guards(header_content)
        types = extract_typedefs_and_structs(header_content)

        # Genera il nuovo contenuto del header
        new_header_content = update_header_file(
            header_content, declarations, includes, guards, types
        )

        # Genera il contenuto del file sorgente
        source_content = generate_source_file(
            header_path, declarations, implementations, includes
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
    header_file = '../' + 'hello-idf/main/he_mgt_string.c'

    if len(sys.argv) > 1:
        header_file = sys.argv[1]

    if not header_file.endswith('.h'):
        print("Il file deve essere un header file .h")
        sys.exit(1)

    process_header_file(header_file)


if __name__ == "__main__":
    main()