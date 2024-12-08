from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Set, List, Optional, DefaultDict, NamedTuple
from collections import defaultdict
import re
import sys
import os

class Symbol(NamedTuple):
    name: str
    kind: str  # 'type', 'variable', 'function'
    line: int
    context: str  # il codice circostante per contesto

@dataclass
class SourceFile:
    path: Path
    includes: List[Path]
    included_by: Set[Path]
    definitions: List[Symbol]  # simboli definiti in questo file
    usages: List[Symbol]      # simboli usati da questo file
    raw_content: Optional[str] = None
    
    def __hash__(self):
        return hash(self.path)
    
    def add_definition(self, name: str, kind: str, line: int, context: str):
        self.definitions.append(Symbol(name, kind, line, context))
    
    def add_usage(self, name: str, kind: str, line: int, context: str):
        self.usages.append(Symbol(name, kind, line, context))

class SourceAnalyzer:
    SOURCE_EXTENSIONS = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.h++'}
    
    def __init__(self, project_paths: List[str]):
        if isinstance(project_paths, str):
            project_paths = [project_paths]
            
        self.project_paths = [Path(p).resolve() for p in project_paths]
        self.files: Dict[Path, SourceFile] = {}
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.symbol_definitions: DefaultDict[str, List[Symbol]] = defaultdict(list)
        self.symbol_usages: DefaultDict[str, List[tuple[Path, Symbol]]] = defaultdict(list)
    
    def analyze(self):
        """Analizza tutti i file sorgente nel progetto."""
        self._find_source_files()
        
        # Prima passa: analizza le definizioni
        for file_path in self.files:
            self._analyze_file(file_path, first_pass=True)
        
        # Seconda passa: analizza gli usi
        for file_path in self.files:
            self._analyze_file(file_path, first_pass=False)
    
    def _find_source_files(self):
        """Trova tutti i file sorgente nelle directory del progetto."""
        found_files = set()
        
        for path in self.project_paths:
            if not path.is_dir():
                print(f"ATTENZIONE: {path} non è una directory valida")
                continue
            
            try:
                for file_path in path.rglob('*'):
                    if self._is_source_file(file_path):
                        found_files.add(file_path)
                        self.files[file_path] = SourceFile(
                            path=file_path,
                            includes=[],
                            included_by=set(),
                            definitions=[],
                            usages=[],
                            raw_content=None
                        )
            except Exception as e:
                print(f"Errore durante la scansione di {path}: {e}")
        
        print(f"\nTrovati {len(found_files)} file sorgente nel progetto:")
        for file_path in sorted(found_files):
            rel_path = self._get_relative_path(file_path)
            print(f"  - {rel_path}")
    
    def _analyze_file(self, file_path: Path, first_pass: bool):
        """Analizza un singolo file per definizioni e usi."""
        try:
            if self.files[file_path].raw_content is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.files[file_path].raw_content = content
            else:
                content = self.files[file_path].raw_content
            
            if first_pass:
                self._analyze_dependencies(file_path, content)
                self._analyze_definitions(file_path, content)
            else:
                self._analyze_usages(file_path, content)
                
        except Exception as e:
            print(f"Errore analizzando {file_path}: {e}")
    
    def _analyze_dependencies(self, file_path: Path, content: str):
        """Analizza le dipendenze di inclusione."""
        source_file = self.files[file_path]
        
        include_pattern = re.compile(r'#include\s*[<"]([^>"]+)[>"]')
        for match in include_pattern.finditer(content):
            included_path = match.group(1)
            resolved_path = self._resolve_include_path(included_path, file_path)
            
            if resolved_path and resolved_path in self.files:
                source_file.includes.append(resolved_path)
                self.files[resolved_path].included_by.add(file_path)
                self.include_graph[file_path].add(resolved_path)
                self.reverse_graph[resolved_path].add(file_path)
    
    def _analyze_definitions(self, file_path: Path, content: str):
        """Analizza le definizioni di tipi e variabili."""
        source_file = self.files[file_path]
        
        # Trova definizioni di struct/class
        struct_pattern = re.compile(r'(struct|class)\s+(\w+)\s*\{', re.MULTILINE)
        for match in struct_pattern.finditer(content):
            name = match.group(2)
            line = content[:match.start()].count('\n') + 1
            context = content[max(0, match.start()-50):match.end()+50]
            source_file.add_definition(name, 'type', line, context)
            self.symbol_definitions[name].append(Symbol(name, 'type', line, context))
        
        # Trova typedef
        typedef_pattern = re.compile(r'typedef\s+(?:struct\s+)?(\w+)(?:\s+\w+)?\s*;', re.MULTILINE)
        for match in typedef_pattern.finditer(content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            context = content[max(0, match.start()-50):match.end()+50]
            source_file.add_definition(name, 'type', line, context)
            self.symbol_definitions[name].append(Symbol(name, 'type', line, context))
        
        # Trova variabili globali
        var_pattern = re.compile(r'(?:extern\s+)?(?:const\s+)?(?:\w+\s+)+(\w+)\s*(?:\[.*?\])?\s*;', re.MULTILINE)
        for match in var_pattern.finditer(content):
            if not re.match(r'^\s*#', content[:match.start()].split('\n')[-1]):  # esclude le macro
                name = match.group(1)
                line = content[:match.start()].count('\n') + 1
                context = content[max(0, match.start()-50):match.end()+50]
                source_file.add_definition(name, 'variable', line, context)
                self.symbol_definitions[name].append(Symbol(name, 'variable', line, context))
        
        # Trova funzioni
        func_pattern = re.compile(r'(?:\w+\s+)+(\w+)\s*\([^;{]*\)\s*\{', re.MULTILINE)
        for match in func_pattern.finditer(content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            context = content[max(0, match.start()-50):match.end()+50]
            source_file.add_definition(name, 'function', line, context)
            self.symbol_definitions[name].append(Symbol(name, 'function', line, context))
    
    def _analyze_usages(self, file_path: Path, content: str):
        """Analizza gli usi di tipi e variabili."""
        source_file = self.files[file_path]
        
        # Per ogni simbolo definito nel progetto, cerca i suoi usi
        for symbol_name, definitions in self.symbol_definitions.items():
            # Cerca usi del simbolo che non siano la sua definizione
            pattern = rf'\b{symbol_name}\b'
            for match in re.finditer(pattern, content):
                line = content[:match.start()].count('\n') + 1
                
                # Verifica che non sia una definizione
                is_definition = any(d.line == line for d in source_file.definitions if d.name == symbol_name)
                if not is_definition:
                    context = content[max(0, match.start()-50):match.end()+50]
                    kind = definitions[0].kind  # usa il tipo del primo simbolo definito
                    source_file.add_usage(symbol_name, kind, line, context)
                    self.symbol_usages[symbol_name].append((file_path, Symbol(symbol_name, kind, line, context)))
    
    def _resolve_include_path(self, included_path: str, current_file: Path) -> Optional[Path]:
        """Risolve il path completo di un file incluso."""
        try:
            relative_path = (current_file.parent / included_path).resolve()
            if relative_path in self.files:
                return relative_path
                
            for project_path in self.project_paths:
                potential_path = (project_path / included_path).resolve()
                if potential_path in self.files:
                    return potential_path
            
            return None
            
        except Exception:
            return None
    
    def _is_source_file(self, file_path: Path) -> bool:
        return (
            file_path.is_file() and
            file_path.suffix.lower() in self.SOURCE_EXTENSIONS and
            not self._is_system_file(file_path)
        )
    
    def _is_system_file(self, file_path: Path) -> bool:
        system_dirs = {'System', 'Library', 'usr', 'include', 'frameworks'}
        return any(part.lower() in system_dirs for part in file_path.parts)
    
    def _get_relative_path(self, file_path: Path) -> Path:
        try:
            return file_path.relative_to(file_path.parent.parent)
        except ValueError:
            return file_path
    
    def print_dependencies(self):
        """Stampa le dipendenze di tutti i file."""
        print("\nDipendenze dei file:")
        for file_path, source_file in sorted(self.files.items()):
            rel_path = self._get_relative_path(file_path)
            print(f"\n{rel_path}:")
            
            if source_file.includes:
                print("  Include:")
                for included in sorted(source_file.includes):
                    print(f"    - {self._get_relative_path(included)}")
            
            if source_file.included_by:
                print("  Incluso da:")
                for including in sorted(source_file.included_by):
                    print(f"    - {self._get_relative_path(including)}")
    
    def print_symbols(self):
        """Stampa i simboli definiti e usati in ogni file."""
        print("\nAnalisi dei simboli:")
        for file_path, source_file in sorted(self.files.items()):
            rel_path = self._get_relative_path(file_path)
            print(f"\n{rel_path}:")
            
            if source_file.definitions:
                print("  Definizioni:")
                for symbol in sorted(source_file.definitions):
                    print(f"    - {symbol.kind} '{symbol.name}' (linea {symbol.line})")
            
            if source_file.usages:
                print("  Usi:")
                for symbol in sorted(source_file.usages):
                    # Trova dove è definito questo simbolo
                    definitions = [
                        (path, sym) 
                        for name, syms in self.symbol_definitions.items() 
                        if name == symbol.name
                        for sym in syms
                        for path in self.files
                        if sym in self.files[path].definitions
                    ]
                    
                    if definitions:
                        def_file, def_sym = definitions[0]
                        print(f"    - {symbol.kind} '{symbol.name}' (linea {symbol.line}) -> definito in {self._get_relative_path(def_file)}:{def_sym.line}")
                    else:
                        print(f"    - {symbol.kind} '{symbol.name}' (linea {symbol.line}) -> definizione non trovata")
    
    def find_cycles(self):
        """Trova e stampa eventuali cicli di inclusione."""
        def dfs(current: Path, visited: Set[Path], path: List[Path]) -> List[List[Path]]:
            if current in path:
                cycle_start = path.index(current)
                return [path[cycle_start:] + [current]]
            
            cycles = []
            for next_file in self.include_graph[current]:
                if next_file not in visited:
                    visited.add(next_file)
                    for cycle in dfs(next_file, visited, path + [current]):
                        cycles.append(cycle)
                    visited.remove(next_file)
            
            return cycles
        
        print("\nRicerca cicli di inclusione:")
        cycles_found = False
        
        for file_path in self.files:
            cycles = dfs(file_path, set(), [])
            for cycle in cycles:
                cycles_found = True
                print("\nCiclo trovato:")
                print("  " + " -> ".join(str(self._get_relative_path(p)) for p in cycle))
        
        if not cycles_found:
            print("Nessun ciclo di inclusione trovato.")

def main():
    project_paths = "../../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3"

    if len(sys.argv) >= 2:
        project_paths = sys.argv[1:]
    
    project_paths = os.path.abspath(project_paths)

    analyzer = SourceAnalyzer(project_paths)
    
    print("Analisi del progetto in corso...")
    analyzer.analyze()
    
    analyzer.print_dependencies()
    analyzer.print_symbols()
    analyzer.find_cycles()

if __name__ == "__main__":
    main()