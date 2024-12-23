#!/usr/bin/env python3
import subprocess

from clang.cindex import Index, CursorKind, TranslationUnit, Config
import re
import os
import sys

def setup_libclang() -> bool:
    """Configura il percorso di libclang per macOS"""
    try:
        brew_prefix = subprocess.check_output(['brew', '--prefix']).decode().strip()
        possible_paths = [
            os.path.join(brew_prefix, 'opt/llvm/lib/libclang.dylib'),
            '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib',
            '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib'
        ]

        for path in possible_paths:
            if os.path.exists(path):
                Config.set_library_file(path)
                return True

        print("ERRORE: libclang non trovato. Installa LLVM:")
        print("brew install llvm")
        return False
    except subprocess.CalledProcessError:
        print("ERRORE: Homebrew non trovato. Installa Homebrew da https://brew.sh")
        return False


class HeaderGenerator:
    def __init__(self):
        self.processed_declarations = set()
        self.processed_includes = set()
        self.type_declarations = {}

    def clean_type_name(self, name: str) -> str:
        """Pulisce il nome del tipo rimuovendo riferimenti non necessari."""
        # Rimuove riferimenti al percorso del file
        name = re.sub(r'at \.\./[^\s}]*:', '', name)
        # Rimuove numeri di riga
        name = re.sub(r':\d+', '', name)
        # Rimuove "unnamed" dalle struct anonime
        name = re.sub(r'struct \(unnamed\s+struct\s+\)', 'struct', name)
        name = re.sub(r'struct \(unnamed\s+at\s+[^)]+\)', 'struct', name)
        return name.strip()

    def extract_includes_and_guards(self, source_content: str) -> tuple:
        """Estrae include e guardie eliminando i duplicati."""
        includes = set()
        guards = []

        lines = source_content.split('\n')
        in_guards = False

        for line in lines:
            line = line.strip()

            if '#ifndef' in line:
                if not in_guards:
                    guards.append(line)
                    in_guards = True
            elif '#define' in line and in_guards:
                guards.append(line)
            elif '#endif' in line and in_guards:
                guards.append(line)
                in_guards = False
            elif '#include' in line:
                # Normalizza e deduplicata gli include
                includes.add(line)

        return list(includes), guards

    def get_struct_declaration(self, cursor) -> str:
        """Genera la dichiarazione di una struct evitando duplicati."""
        struct_name = self.clean_type_name(cursor.spelling or "unnamed")

        # Se questa struct è già stata processata, salta
        if struct_name in self.processed_declarations:
            return ""

        self.processed_declarations.add(struct_name)

        # Costruisci la dichiarazione
        fields = []
        for field in cursor.get_children():
            if field.kind == CursorKind.FIELD_DECL:
                field_type = self.clean_type_name(field.type.spelling)
                fields.append(f"    {field_type} {field.spelling};")

        if not fields:  # struct vuota
            return f"typedef struct {struct_name} {{ }} {struct_name};\n"

        return f"typedef struct {struct_name} {{\n" + \
            "\n".join(fields) + \
            f"\n}} {struct_name};\n"

    def get_function_declaration(self, cursor) -> str:
        """Genera la dichiarazione di una funzione."""
        func_signature = f"{cursor.result_type.spelling} {cursor.spelling}"

        # Se questa funzione è già stata processata, salta
        if func_signature in self.processed_declarations:
            return ""

        self.processed_declarations.add(func_signature)

        args = []
        for arg in cursor.get_arguments():
            arg_type = self.clean_type_name(arg.type.spelling)
            args.append(f"{arg_type} {arg.spelling}")

        return f"{cursor.result_type.spelling} {cursor.spelling}({', '.join(args)});\n"

    def generate_header(self, source_file: str) -> str:
        """Genera il contenuto del file header."""
        index = Index.create()

        with open(source_file, 'r') as f:
            source_content = f.read()

        includes, guards = self.extract_includes_and_guards(source_content)

        # Parsing del file
        tu = index.parse(source_file)

        # Organizza il contenuto dell'header
        header_content = []

        # Aggiungi le guardie dell'header
        if guards:
            header_content.extend(guards[:2])
        else:
            header_name = os.path.basename(source_file).upper().replace('.', '_')
            header_content.extend([
                f"#ifndef {header_name}",
                f"#define {header_name}"
            ])

        # Aggiungi gli include deduplicati
        header_content.extend(sorted(includes))
        header_content.append("")

        # Raccogli tutte le dichiarazioni
        declarations = []

        for cursor in tu.cursor.walk_preorder():
            if cursor.kind == CursorKind.STRUCT_DECL:
                decl = self.get_struct_declaration(cursor)
                if decl:
                    declarations.append(decl)
            elif cursor.kind == CursorKind.FUNCTION_DECL and not cursor.is_definition():
                decl = self.get_function_declaration(cursor)
                if decl:
                    declarations.append(decl)

        # Aggiungi le dichiarazioni deduplicate
        header_content.extend(declarations)

        # Chiudi le guardie dell'header
        if guards:
            header_content.append(guards[-1])
        else:
            header_content.append("#endif")

        return "\n".join(header_content)

    def update_source_file(self, source_file: str) -> None:
        """Aggiorna il file sorgente."""
        header_name = os.path.basename(source_file).replace('.c', '.h')

        with open(source_file, 'r') as f:
            content = f.read()

        # Rimuovi le guardie e le dichiarazioni
        content = re.sub(r'#ifndef.*?\n#define.*?\n.*?#endif', '',
                         content, flags=re.DOTALL)

        # Aggiungi l'include del nuovo header
        include_statement = f'#include "{header_name}"\n'
        if include_statement not in content:
            content = include_statement + content

        with open(source_file, 'w') as f:
            f.write(content)


def main():
    source_file = '../'+ 'hello-idf/main/he_mgt_string.c'

    if len(sys.argv) > 1:
        source_file = sys.argv[1]

    if not source_file.endswith('.c'):
        print("Il file deve essere un file sorgente .c")
        sys.exit(1)

    if not setup_libclang():
        raise RuntimeError("Impossibile inizializzare libclang")


    header_file = source_file.replace('.c', '.h')

    try:
        generator = HeaderGenerator()

        # Genera il contenuto dell'header
        header_content = generator.generate_header(source_file)

        # Scrivi il file header
        with open(header_file, 'w') as f:
            f.write(header_content)

        # Aggiorna il file sorgente
        generator.update_source_file(source_file)

        print(f"File header generato: {header_file}")
        print(f"File sorgente aggiornato: {source_file}")

    except Exception as e:
        print(f"Errore durante la generazione: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()