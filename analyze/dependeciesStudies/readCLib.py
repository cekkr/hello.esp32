from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, DefaultDict, NamedTuple, Tuple
from collections import defaultdict
import re
import sys
import os
import subprocess
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config

class Symbol(NamedTuple):
    name: str
    kind: str  # 'type', 'variable', 'function', 'macro'
    line: int
    context: str
    cursor_kind: Optional[CursorKind] = None

@dataclass
class SourceFile:
    path: Path
    includes: List[Path]
    included_by: Set[Path]
    definitions: List[Symbol]
    usages: List[Symbol]
    raw_content: Optional[str] = None
    is_header: bool = False
    
    def __hash__(self):
        return hash(self.path)
    
    def add_definition(self, name: str, kind: str, line: int, context: str, cursor_kind: Optional[CursorKind] = None):
        self.definitions.append(Symbol(name, kind, line, context, cursor_kind))
    
    def add_usage(self, name: str, kind: str, line: int, context: str, cursor_kind: Optional[CursorKind] = None):
        self.usages.append(Symbol(name, kind, line, context, cursor_kind))

def setup_libclang() -> bool:
    """Configura il percorso di libclang."""
    try:
        # Prova prima con brew su macOS
        try:
            brew_prefix = subprocess.check_output(['brew', '--prefix']).decode().strip()
            possible_paths = [
                os.path.join(brew_prefix, 'opt/llvm/lib/libclang.dylib'),
                '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib',
                '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib',
                '/usr/lib/llvm-14/lib/libclang.so.1',  # Linux
                '/usr/lib/llvm-14/lib/libclang.so'
            ]
        except subprocess.CalledProcessError:
            possible_paths = [
                '/usr/lib/llvm-14/lib/libclang.so.1',  # Linux
                '/usr/lib/llvm-14/lib/libclang.so'
            ]
        
        for path in possible_paths:
            if os.path.exists(path):
                Config.set_library_file(path)
                return True
        
        print("ERRORE: libclang non trovato. Installa LLVM:")
        print("  macOS: brew install llvm")
        print("  Linux: sudo apt install libclang1")
        return False
    except Exception as e:
        print(f"ERRORE: {e}")
        return False

class SourceAnalyzer:
    SOURCE_EXTENSIONS = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.h++'}
    
    def __init__(self, project_paths: List[str]):
        if isinstance(project_paths, str):
            project_paths = [project_paths]
            
        self.project_paths = [Path(p) for p in project_paths] # Path(p).resolve()
        self.files: Dict[Path, SourceFile] = {}
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.symbol_definitions: DefaultDict[str, List[Symbol]] = defaultdict(list)
        self.symbol_usages: DefaultDict[str, List[tuple[Path, Symbol]]] = defaultdict(list)
        
        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        self.index = Index.create()
    
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
                        is_header = file_path.suffix.lower() in {'.h', '.hpp', '.hxx', '.h++'}
                        self.files[file_path] = SourceFile(
                            path=file_path,
                            includes=[],
                            included_by=set(),
                            definitions=[],
                            usages=[],
                            raw_content=None,
                            is_header=is_header
                        )
            except Exception as e:
                print(f"Errore durante la scansione di {path}: {e}")
        
        print(f"\nTrovati {len(found_files)} file sorgente nel progetto:")
        for file_path in sorted(found_files):
            rel_path = self._get_relative_path(file_path)
            print(f"  - {rel_path}")
    
    def _analyze_file(self, file_path: Path, first_pass: bool):
        """Analizza un singolo file usando libclang."""
        try:
            source_file = self.files[file_path]
            
            if source_file.raw_content is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_file.raw_content = f.read()
            
            # Usa libclang per il parsing
            translation_unit = self.index.parse(
                str(file_path),
                args=['-x', 'c++'] if file_path.suffix in {'.cpp', '.hpp'} else ['-x', 'c']
            )
            
            if first_pass:
                self._analyze_includes(translation_unit, source_file)
                self._analyze_definitions(translation_unit.cursor, source_file)
            else:
                self._analyze_usages(translation_unit.cursor, source_file)
                
        except Exception as e:
            print(f"Errore analizzando {file_path}: {e}")
    
    def _analyze_includes(self, translation_unit, source_file: SourceFile):
        """Analizza le direttive #include usando libclang."""
        for include in translation_unit.get_includes():
            included_path = Path(include.include.name)
            resolved_path = self._resolve_include_path(included_path, source_file.path)
            
            if resolved_path and resolved_path in self.files:
                source_file.includes.append(resolved_path)
                self.files[resolved_path].included_by.add(source_file.path)
                self.include_graph[source_file.path].add(resolved_path)
                self.reverse_graph[resolved_path].add(source_file.path)
    
    def _analyze_definitions(self, cursor, source_file: SourceFile):
        """Analizza le definizioni usando il cursore di libclang."""
        if cursor.location.file and Path(cursor.location.file.name) == source_file.path:
            line = cursor.location.line
            # Estrai il contesto (50 caratteri prima e dopo)
            context = self._get_context(source_file.raw_content, line)
            
            if cursor.kind in {CursorKind.TYPEDEF_DECL, CursorKind.STRUCT_DECL, 
                             CursorKind.CLASS_DECL, CursorKind.ENUM_DECL}:
                source_file.add_definition(cursor.spelling, 'type', line, context, cursor.kind)
                self.symbol_definitions[cursor.spelling].append(
                    Symbol(cursor.spelling, 'type', line, context, cursor.kind)
                )
                
            elif cursor.kind == CursorKind.FUNCTION_DECL:
                source_file.add_definition(cursor.spelling, 'function', line, context, cursor.kind)
                self.symbol_definitions[cursor.spelling].append(
                    Symbol(cursor.spelling, 'function', line, context, cursor.kind)
                )
                
            elif cursor.kind == CursorKind.VAR_DECL:
                if cursor.storage_class in {clang.cindex.StorageClass.EXTERN, clang.cindex.StorageClass.STATIC}:
                    source_file.add_definition(cursor.spelling, 'variable', line, context, cursor.kind)
                    self.symbol_definitions[cursor.spelling].append(
                        Symbol(cursor.spelling, 'variable', line, context, cursor.kind)
                    )
                
            elif cursor.kind == CursorKind.MACRO_DEFINITION:
                source_file.add_definition(cursor.spelling, 'macro', line, context, cursor.kind)
                self.symbol_definitions[cursor.spelling].append(
                    Symbol(cursor.spelling, 'macro', line, context, cursor.kind)
                )
        
        for child in cursor.get_children():
            self._analyze_definitions(child, source_file)
    
    def _analyze_usages(self, cursor, source_file: SourceFile):
        """Analizza gli usi dei simboli usando il cursore di libclang."""
        if cursor.location.file and Path(cursor.location.file.name) == source_file.path:
            line = cursor.location.line
            context = self._get_context(source_file.raw_content, line)
            
            if cursor.referenced and cursor.referenced.spelling:
                ref_kind = cursor.referenced.kind
                symbol_name = cursor.referenced.spelling
                
                # Verifica che non sia una definizione
                is_definition = any(
                    d.line == line and d.name == symbol_name 
                    for d in source_file.definitions
                )
                
                if not is_definition:
                    kind = self._get_symbol_kind(ref_kind)
                    if kind:
                        source_file.add_usage(symbol_name, kind, line, context, ref_kind)
                        self.symbol_usages[symbol_name].append(
                            (source_file.path, Symbol(symbol_name, kind, line, context, ref_kind))
                        )
        
        for child in cursor.get_children():
            self._analyze_usages(child, source_file)
    
    def _get_symbol_kind(self, cursor_kind: CursorKind) -> Optional[str]:
        """Converte il tipo di cursore in un tipo di simbolo."""
        if cursor_kind in {CursorKind.TYPEDEF_DECL, CursorKind.STRUCT_DECL, 
                          CursorKind.CLASS_DECL, CursorKind.ENUM_DECL}:
            return 'type'
        elif cursor_kind == CursorKind.FUNCTION_DECL:
            return 'function'
        elif cursor_kind == CursorKind.VAR_DECL:
            return 'variable'
        elif cursor_kind == CursorKind.MACRO_DEFINITION:
            return 'macro'
        return None
    
    def _get_context(self, content: str, line: int, context_size: int = 50) -> str:
        """Estrae il contesto attorno a una linea specifica."""
        lines = content.splitlines()
        if 1 <= line <= len(lines):
            target_line = lines[line - 1]
            return target_line.strip()
        return ""
    
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
                    print(f"    - {symbol.kind} '{symbol.name}' "
                          f"(linea {symbol.line})")
                    if symbol.context:
                        print(f"      {symbol.context}")
            
            if source_file.usages:
                print("  Usi:")
                for symbol in sorted(source_file.usages):
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
                        print(f"    - {symbol.kind} '{symbol.name}' "
                              f"(linea {symbol.line}) -> "
                              f"definito in {self._get_relative_path(def_file)}:{def_sym.line}")
                        if symbol.context:
                            print(f"      Uso: {symbol.context}")
                            print(f"      Definizione: {def_sym.context}")
                    else:
                        print(f"    - {symbol.kind} '{symbol.name}' "
                              f"(linea {symbol.line}) -> definizione non trovata")
                        if symbol.context:
                            print(f"      Uso: {symbol.context}")
    
    def analyze_symbol(self, symbol_name: str):
        """Analizza in dettaglio un simbolo specifico."""
        print(f"\n=== Analisi dettagliata del simbolo '{symbol_name}' ===\n")
        
        # Trova le definizioni
        definitions = self.symbol_definitions.get(symbol_name, [])
        if definitions:
            print("Definizioni trovate:")
            for def_sym in definitions:
                # Trova il file che contiene questa definizione
                def_file = next(
                    path for path in self.files
                    if def_sym in self.files[path].definitions
                )
                print(f"\n  In {self._get_relative_path(def_file)}:{def_sym.line}")
                print(f"  Tipo: {def_sym.kind}")
                if def_sym.cursor_kind:
                    print(f"  Tipo Clang: {def_sym.cursor_kind}")
                print(f"  Contesto: {def_sym.context}")
                
                # Mostra i file che includono questa definizione
                if def_file in self.reverse_graph:
                    including_files = self.reverse_graph[def_file]
                    if including_files:
                        print("\n  Accessibile attraverso:")
                        for inc_file in sorted(including_files):
                            print(f"    - {self._get_relative_path(inc_file)}")
        
        # Trova gli usi
        usages = self.symbol_usages.get(symbol_name, [])
        if usages:
            print("\nUtilizzi trovati:")
            for use_file, use_sym in sorted(usages):
                print(f"\n  In {self._get_relative_path(use_file)}:{use_sym.line}")
                print(f"  Contesto: {use_sym.context}")
                
                # Verifica il percorso di inclusione verso la definizione
                if definitions:
                    def_file = next(
                        path for path in self.files
                        if definitions[0] in self.files[path].definitions
                    )
                    paths = self.find_include_paths(use_file, def_file)
                    if paths:
                        print("\n  Percorso di inclusione:")
                        for path in paths[0]:  # Mostra solo il primo percorso trovato
                            print(f"    - {self._get_relative_path(path)}")
                    else:
                        print("\n  ATTENZIONE: Nessun percorso di inclusione trovato!")
        
        if not definitions and not usages:
            print(f"Nessuna informazione trovata per il simbolo '{symbol_name}'")
    
    def find_include_paths(self, from_file: Path, to_file: Path, 
                          max_depth: int = 10) -> List[List[Path]]:
        """Trova tutti i percorsi di inclusione tra due file."""
        def dfs(current: Path, target: Path, visited: Set[Path], 
                path: List[Path], depth: int) -> List[List[Path]]:
            if depth > max_depth:
                return []
            
            if current == target:
                return [path + [current]]
            
            if current in visited:
                return []
            
            paths = []
            visited.add(current)
            
            for next_file in self.include_graph[current]:
                for new_path in dfs(next_file, target, visited.copy(), 
                                  path + [current], depth + 1):
                    paths.append(new_path)
            
            return paths
        
        return dfs(from_file, to_file, set(), [], 0)
    
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
    
    def suggest_missing_includes(self):
        """Suggerisce include mancanti basandosi sull'analisi dei simboli."""
        print("\nAnalisi degli #include mancanti:")
        
        for file_path, source_file in sorted(self.files.items()):
            missing_includes = set()
            
            # Per ogni simbolo usato
            for usage in source_file.usages:
                # Trova dove è definito il simbolo
                definitions = [
                    (path, sym) 
                    for name, syms in self.symbol_definitions.items() 
                    if name == usage.name
                    for sym in syms
                    for path in self.files
                    if sym in self.files[path].definitions
                ]
                
                if definitions:
                    def_file, _ = definitions[0]
                    # Se il file di definizione non è incluso direttamente o indirettamente
                    if not self._is_symbol_accessible(usage.name, file_path):
                        missing_includes.add(def_file)
            
            if missing_includes:
                rel_path = self._get_relative_path(file_path)
                print(f"\n{rel_path} potrebbe necessitare di:")
                for inc in sorted(missing_includes):
                    print(f"  #include \"{self._get_relative_path(inc)}\"")
    
    def _is_symbol_accessible(self, symbol_name: str, from_file: Path, 
                            visited: Optional[Set[Path]] = None) -> bool:
        """Verifica se un simbolo è accessibile da un file attraverso gli include."""
        if visited is None:
            visited = set()
        
        if from_file in visited:
            return False
        
        visited.add(from_file)
        
        # Verifica se il simbolo è definito nel file corrente
        current_file = self.files[from_file]
        if any(d.name == symbol_name for d in current_file.definitions):
            return True
        
        # Verifica ricorsivamente nei file inclusi
        for included in current_file.includes:
            if self._is_symbol_accessible(symbol_name, included, visited):
                return True
        
        return False
