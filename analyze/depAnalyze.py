from dataclasses import dataclass
from typing import Dict, Set, List, Optional
from pathlib import Path
import os
import re
import networkx as nx
from collections import defaultdict

def check_directory(directory_path: str):
    """Verifica dettagliatamente una directory e mostra il suo contenuto"""
    # Converti in percorso assoluto
    abs_path = os.path.abspath(directory_path)
    print(f"\nVerifica directory: {abs_path}")
    
    # Informazioni sul percorso corrente di esecuzione
    print(f"Directory corrente di esecuzione: {os.getcwd()}")
    
    if not os.path.exists(abs_path):
        print(f"ERRORE: Il percorso {abs_path} non esiste!")
        return
    
    print("\nContenuto directory:")
    for root, dirs, files in os.walk(abs_path):
        level = root.replace(abs_path, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = '  ' * (level + 1)
        
        # Prima stampa le directory
        for d in dirs:
            print(f"{sub_indent}[DIR] {d}")
        
        # Poi stampa i file
        for f in files:
            full_path = os.path.join(root, f)
            size = os.path.getsize(full_path)
            print(f"{sub_indent}[FILE] {f} ({size} bytes)")
            
            # Se è un file .h, mostra le prime righe
            if f.endswith('.h'):
                try:
                    with open(full_path, 'r', encoding='utf-8') as file:
                        first_lines = file.readlines()[:3]
                        print(f"{sub_indent}  Prime righe:")
                        for line in first_lines:
                            print(f"{sub_indent}    {line.rstrip()}")
                except Exception as e:
                    print(f"{sub_indent}  Errore lettura: {e}")

@dataclass
class TypeDefinition:
    """Rappresenta un tipo definito (struct/class/enum)"""
    name: str
    kind: str  # 'struct', 'class', 'enum'
    file_path: str
    line_number: int
    dependencies: Set[str]  # altri tipi da cui dipende
    forward_declarations: Set[str]  # file dove è forward-declared

@dataclass
class HeaderFile:
    """Rappresenta un file header e il suo contenuto"""
    path: Path
    includes: List[str]
    types_defined: Dict[str, TypeDefinition]  # nome tipo -> definizione
    types_used: Set[str]  # tipi usati ma non definiti qui
    forward_declarations: Set[str]  # tipi forward-declared qui

class HeaderAnalyzer:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.headers: Dict[Path, HeaderFile] = {}
        self.dependency_graph = nx.DiGraph()
        
        # Directory da escludere
        self.excluded_dirs = {
            'build', 'builds', '.git', '.svn', '__pycache__', 
            'sdkconfig', 'bootloader'
        }
    
    def find_headers(self) -> List[Path]:
        """Trova tutti i file .h ricorsivamente usando multiple strategie"""
        headers = set()  # Usa un set per evitare duplicati
        print(f"\nCercando header files in: {self.base_path}")

        # Converti il percorso base in assoluto
        abs_base_path = self.base_path.resolve()
        print(f"Percorso assoluto: {abs_base_path}")

        def is_excluded(path: Path) -> bool:
            """Verifica se un percorso deve essere escluso"""
            return any(excluded in path.parts for excluded in self.excluded_dirs)

        def add_header(path: Path):
            """Aggiunge un header alla lista se non è già presente e non è escluso"""
            if not is_excluded(path):
                abs_path = path.resolve()
                headers.add(abs_path)
                print(f"Trovato header: {abs_path}")

        # Strategia 1: Usa Path.rglob
        try:
            for pattern in ['*.h', '*.hpp', '*.hxx']:
                for file_path in abs_base_path.rglob(pattern):
                    add_header(file_path)
        except Exception as e:
            print(f"Errore durante rglob: {e}")

        # Strategia 2: Usa os.walk con gestione symlink
        try:
            for root, dirs, files in os.walk(abs_base_path, followlinks=True):
                # Filtra le directory da escludere
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                
                root_path = Path(root)
                
                # Gestisce i file
                for file in files:
                    if file.endswith(('.h', '.hpp', '.hxx')):
                        file_path = root_path / file
                        try:
                            add_header(file_path)
                        except Exception as e:
                            print(f"Errore nell'aggiunta del file {file_path}: {e}")
                
                # Verifica symlink nelle directory
                for dir_name in dirs:
                    dir_path = root_path / dir_name
                    if dir_path.is_symlink():
                        try:
                            real_path = dir_path.resolve()
                            if real_path != dir_path:
                                print(f"Seguendo symlink: {dir_path} -> {real_path}")
                                # Cerca ricorsivamente nel target del symlink
                                for pattern in ['*.h', '*.hpp', '*.hxx']:
                                    for linked_file in real_path.rglob(pattern):
                                        add_header(linked_file)
                        except Exception as e:
                            print(f"Errore nel seguire symlink {dir_path}: {e}")

        except Exception as e:
            print(f"Errore durante walk: {e}")

        # Strategia 3: Cerca anche nella directory corrente e parent
        try:
            current_dir = Path.cwd()
            parent_dir = current_dir.parent
            
            for search_dir in [current_dir, parent_dir]:
                for pattern in ['*.h', '*.hpp', '*.hxx']:
                    for file_path in search_dir.glob(pattern):
                        if abs_base_path in file_path.resolve().parents:
                            add_header(file_path)
        except Exception as e:
            print(f"Errore durante la ricerca nelle directory parent: {e}")

        # Converti il set in lista e ordina per path
        header_list = sorted(list(headers))
        
        # Stampa statistiche finali
        print(f"\nStatistiche di ricerca:")
        print(f"Totale header trovati: {len(header_list)}")
        print(f"Directory esplorate: {len({h.parent for h in header_list})}")
        
        return header_list

    def analyze_file(self, file_path: Path) -> HeaderFile:
        """Analizza un singolo file header"""
        print(f"\nAnalizzando file: {file_path}")
        
        header = HeaderFile(
            path=file_path,
            includes=[],
            types_defined={},
            types_used=set(),
            forward_declarations=set()
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Trova gli #include
            header.includes = self._find_includes(content)
            print(f"Include trovati: {header.includes}")
            
            # Trova le definizioni di tipo
            header.types_defined = self._find_type_definitions(content, str(file_path))
            print(f"Tipi definiti: {list(header.types_defined.keys())}")
            
            # Trova i forward declarations
            header.forward_declarations = self._find_forward_declarations(content)
            print(f"Forward declarations: {header.forward_declarations}")
            
            # Trova i tipi usati
            header.types_used = self._find_used_types(content)
            print(f"Tipi usati: {header.types_used}")
            
        except Exception as e:
            print(f"Errore nell'analisi del file {file_path}: {e}")
        
        return header

    def _find_includes(self, content: str) -> List[str]:
        """Trova tutti gli #include nel file"""
        includes = []
        for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
            includes.append(match.group(1))
        return includes    

    def _find_forward_declarations(self, content: str) -> Set[str]:
        """Trova tutte le forward declarations nel file"""
        declarations = set()
        pattern = r'(?:struct|class|enum)\s+(\w+)\s*;'
        
        for match in re.finditer(pattern, content):
            declarations.add(match.group(1))
        
        return declarations

    def _find_used_types(self, content: str) -> Set[str]:
        """Trova tutti i tipi usati nel file"""
        used_types = set()
        # Cerca riferimenti a struct/class/enum
        pattern = r'(?:struct|class|enum)\s+(\w+)(?:\s+|\*|\&)'
        
        for match in re.finditer(pattern, content):
            used_types.add(match.group(1))
        
        return used_types

    def build_dependency_graph(self):
        """Costruisce il grafo delle dipendenze tra i tipi"""
        for header in self.headers.values():
            for type_name, type_def in header.types_defined.items():
                for dep in type_def.dependencies:
                    self.dependency_graph.add_edge(type_name, dep)

    def find_circular_dependencies(self) -> List[List[str]]:
        """Trova tutte le dipendenze circolari"""
        return list(nx.simple_cycles(self.dependency_graph))

    def generate_suggestions(self) -> Dict[str, List[str]]:
        """Genera suggerimenti per risolvere le dipendenze circolari"""
        suggestions = defaultdict(list)
        cycles = self.find_circular_dependencies()
        
        for cycle in cycles:
            # Analizza ogni ciclo
            for type_name in cycle:
                # Trova il file dove è definito il tipo
                definition_file = None
                for header in self.headers.values():
                    if type_name in header.types_defined:
                        definition_file = header.path
                        break
                
                if definition_file:
                    # Genera suggerimenti
                    suggestions[str(definition_file)].extend([
                        f"Ciclo trovato: {' -> '.join(cycle)}",
                        f"Considerare di creare forward declaration per '{type_name}'",
                        "Possibili soluzioni:",
                        f"1. Sposta la definizione di '{type_name}' in un nuovo file",
                        "2. Usa puntatori o riferimenti invece di inclusione diretta",
                        f"3. Crea un header '{type_name}_fwd.h' con forward declarations"
                    ])
        
        return suggestions

    def analyze(self):
        """Esegue l'analisi completa"""
        # Trova tutti i file header
        print("=== Ricerca file header ===")
        header_files = self.find_headers()
        
        # Analizza ogni file
        print("\n=== Analisi dei file ===")
        for file_path in header_files:
            self.headers[file_path] = self.analyze_file(file_path)
        
        # Costruisci il grafo delle dipendenze
        print("\n=== Costruzione grafo dipendenze ===")
        self.build_dependency_graph()
        
        # Trova le dipendenze circolari
        print("\n=== Analisi dipendenze circolari ===")
        cycles = self.find_circular_dependencies()
        if cycles:
            print("Dipendenze circolari trovate:")
            for cycle in cycles:
                print(f"  {' -> '.join(cycle)}")
        else:
            print("Nessuna dipendenza circolare trovata")
        
        # Genera suggerimenti
        print("\n=== Suggerimenti ===")
        suggestions = self.generate_suggestions()
        for file_path, file_suggestions in suggestions.items():
            print(f"\nPer il file {file_path}:")
            for suggestion in file_suggestions:
                print(f"  {suggestion}")

    def _find_type_definitions(self, content: str, file_path: str) -> Dict[str, TypeDefinition]:
        """Trova tutte le definizioni di tipo nel file"""
        definitions = {}
        
        # Rimuovi i commenti per semplificare il parsing
        content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content_no_comments = re.sub(r'//.*$', '', content_no_comments, flags=re.MULTILINE)
        
        # Pattern più robusto per le definizioni di tipo
        type_pattern = r'''
            # Tipo di definizione
            (struct|class|enum)\s+
            # Template opzionale
            (?:template\s*<[^>]*>\s*)?
            # Nome del tipo
            (\w+)\s*
            # Eredità opzionale
            (?::\s*(?:public|private|protected)\s+\w+(?:\s*,\s*(?:public|private|protected)\s+\w+)*\s*)?
            # Attributi opzionali
            (?:__attribute__\s*\(\([^)]*\)\)\s*)*
            # Corpo della definizione
            {([^{}]*(?:{[^{}]*}[^{}]*)*)}
        '''
        
        for match in re.finditer(type_pattern, content_no_comments, re.VERBOSE):
            kind, name, body = match.groups()
            line_number = content[:match.start()].count('\n') + 1
            
            # Pattern migliorato per trovare le dipendenze
            dependencies = set()
            
            # Trova riferimenti a struct/class/enum
            dep_pattern = r'''
                # Tipi di base
                (?:struct|class|enum)\s+(\w+)|
                # Template parameters
                (?:typename|class)\s+(\w+)|
                # Tipi usati come membri
                (?:^|[^:\w])(\w+)(?:\s*[*&]|\s+\w+\s*[;{])
            '''
            
            for dep_match in re.finditer(dep_pattern, body, re.VERBOSE | re.MULTILINE):
                dep_name = next(g for g in dep_match.groups() if g)
                if dep_name != name and not dep_name.startswith('_'):  # Ignora auto-riferimenti e tipi interni
                    dependencies.add(dep_name)
            
            definitions[name] = TypeDefinition(
                name=name,
                kind=kind,
                file_path=file_path,
                line_number=line_number,
                dependencies=dependencies,
                forward_declarations=set()
            )
        
        return definitions

def main():
    # Imposta il percorso base
    base_path = '../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi'
    
    try:
        # Crea e esegui l'analizzatore
        analyzer = HeaderAnalyzer(base_path)
        analyzer.analyze()
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")

if __name__ == "__main__":
    main()