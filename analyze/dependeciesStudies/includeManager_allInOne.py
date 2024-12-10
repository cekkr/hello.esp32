from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional, Callable
from pathlib import Path
from collections import defaultdict
import contextlib
from readCLib import *
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
    available_types: Set[str] = field(default_factory=set)  # Tipi disponibili nel contesto
    
    def __hash__(self):
        return hash(self.path)
    
    def add_definition(self, name: str, kind: str, line: int, context: str, cursor_kind: Optional[CursorKind] = None):
        symbol = Symbol(name, kind, line, context, cursor_kind)
        self.definitions.append(symbol)
        if kind == 'type':
            self.available_types.add(name)
    
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


@dataclass
class SymbolDefinition:
    """Enhanced symbol definition with scope and dependency information"""
    name: str
    kind: str
    file: Path
    line: int
    scope: str
    dependencies: Set[str] = field(default_factory=set)
    is_exported: bool = True

@dataclass
class SymbolUsage:
    """Track where and how symbols are used"""
    name: str
    file: Path
    line: int
    context: str
    required_symbols: Set[str] = field(default_factory=set)

@dataclass
class SymbolTable:
    """Global symbol management"""
    definitions: Dict[str, List[SymbolDefinition]] = field(default_factory=lambda: defaultdict(list))
    usages: Dict[str, List[SymbolUsage]] = field(default_factory=lambda: defaultdict(list))
    dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def __init__(self):
        self.dependencies = {}
        self.usages = {}
        self.definitions = {}
        self.dependenciesCache: Dict[str, object] = {}

    def add_definition(self, symbol: SymbolDefinition):
        if symbol.name not in self.definitions:
            self.definitions[symbol.name] = []

        self.definitions[symbol.name].append(symbol)

    def check_dependency(self, dep: str):
        if dep not in self.dependencies:
            self.dependencies[dep] = set()

    def add_usage(self, usage: SymbolUsage):
        if usage.name not in self.usages:
            self.usages[usage.name] = []

        self.usages[usage.name].append(usage)
        # Update symbol dependencies
        for req in usage.required_symbols:
            self.check_dependency(usage.name)
            self.dependencies[usage.name].add(req)
    
    def get_symbol_providers(self, symbol_name: str) -> List[Path]:
        """Get all files that provide a given symbol"""
        return [def_.file for def_ in self.definitions.get(symbol_name, [])]

    def get_symbol_dependencies(self, symbol_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """
        Get all symbols that a given symbol depends on, avoiding circular dependencies.

        Args:
            symbol_name: Name of the symbol to analyze
            visited: Set of already visited symbols in the current recursion path

        Returns:
            Set of all dependent symbols
        """

        if symbol_name in self.dependenciesCache:
            return self.dependenciesCache[symbol_name]

        print("get_symbol_dependencies: ", symbol_name, visited)

        # Initialize visited set on first call
        if visited is None:
            visited = set()

        # Check for circular dependency
        if symbol_name in visited:
            return set()  # Break the cycle

        # Mark current symbol as visited
        visited.add(symbol_name)

        # Get direct dependencies
        direct_deps = self.dependencies.get(symbol_name, set())
        all_deps = set(direct_deps)

        # Recursively get transitive dependencies
        for dep in direct_deps:
            # Only recurse if we haven't seen this dependency yet
            if dep not in visited:
                # Pass the visited set to track the full recursion path
                all_deps.update(self.get_symbol_dependencies(dep, visited))

        # Remove current symbol from visited when backtracking
        visited.remove(symbol_name)

        self.dependenciesCache[symbol_name] = all_deps

        return all_deps

    # Alternative implementation using a context manager for better readability
    @contextlib.contextmanager
    def _track_dependency_path(self, symbol: str, path: Set[str]):
        """Context manager to track dependency path and handle cleanup"""
        path.add(symbol)
        try:
            yield
        finally:
            path.remove(symbol)

    def get_symbol_dependencies_alt(self, symbol_name: str, _path: Optional[Set[str]] = None) -> Set[str]:
        """
        Alternative implementation using a context manager for cleaner recursion tracking.

        Args:
            symbol_name: Name of the symbol to analyze
            _path: Internal parameter to track recursion path

        Returns:
            Set of all dependent symbols
        """
        # Initialize tracking set on first call
        if _path is None:
            _path = set()

        # Check for circular dependency
        if symbol_name in _path:
            return set()  # Break the cycle

        all_deps = set()

        # Use context manager to track current symbol in path
        with self._track_dependency_path(symbol_name, _path):
            # Get direct dependencies
            direct_deps = self.dependencies.get(symbol_name, set())
            all_deps.update(direct_deps)

            # Recursively get transitive dependencies
            for dep in direct_deps:
                if dep not in _path:  # Only recurse if not creating a cycle
                    all_deps.update(self.get_symbol_dependencies_alt(dep, _path))

        return all_deps

@dataclass
class HeaderDependencies:
    """Track header file dependencies and symbols"""
    path: Path
    provided_symbols: Set[str] = field(default_factory=set)
    required_symbols: Set[str] = field(default_factory=set)
    direct_includes: Set[Path] = field(default_factory=set)
    transitive_includes: Set[Path] = field(default_factory=set)
    dependents: Set[Path] = field(default_factory=set)
    
    def add_provided_symbol(self, symbol: str):
        self.provided_symbols.add(symbol)
        
    def add_required_symbol(self, symbol: str):
        self.required_symbols.add(symbol)
        
    def add_include(self, header: Path):
        self.direct_includes.add(header)


class ImprovedIncludeResolver:
    def __init__(self, source_files: Dict[Path, SourceFile]):
        self.source_files = source_files
        self.symbol_table = SymbolTable()
        self.header_deps: Dict[Path, HeaderDependencies] = {}
        self.include_order: Dict[Path, List[Path]] = {}
        self.available_types: Dict[Path, Set[str]] = {}  # Cache dei tipi disponibili per file
        
    def _calculate_available_types(self, file_path: Path, visited: Optional[Set[Path]] = None) -> Set[str]:
        """Calcola ricorsivamente i tipi disponibili per un file"""
        if visited is None:
            visited = set()
            
        if file_path in self.available_types:
            return self.available_types[file_path]
            
        if file_path in visited:
            return set()
            
        visited.add(file_path)
        source = self.source_files[file_path]
        available = set(source.available_types)
        
        # Aggiungi i tipi dagli include in ordine
        for include in source.includes:
            if include in self.source_files:
                available.update(self._calculate_available_types(include, visited))
                
        self.available_types[file_path] = available
        return available
    
    def _check_type_dependencies(self, source: SourceFile) -> Set[str]:
        """Verifica le dipendenze dei tipi per un file"""
        required_types = set()
        
        # Estrai i tipi richiesti dalle definizioni
        for def_ in source.definitions:
            if def_.kind == 'type':
                context_types = self._extract_type_dependencies(def_.context)
                required_types.update(context_types)
                
        # Estrai i tipi richiesti dagli usi
        for usage in source.usages:
            context_types = self._extract_type_dependencies(usage.context)
            required_types.update(context_types)
            
        return required_types
    
    def _extract_type_dependencies(self, context: str) -> Set[str]:
        """Estrae le dipendenze di tipo dal contesto"""
        type_deps = set()
        words = re.findall(r'\b\w+\b', context)
        
        for word in words:
            # Verifica se il word è un tipo conosciuto
            if any(word in self.source_files[file].available_types 
                  for file in self.source_files):
                type_deps.add(word)
                
        return type_deps
    
    def _resolve_include_order(self):
        """Determina l'ordine ottimale di inclusione considerando le dipendenze dei tipi"""
        # Resetta l'ordine e la cache
        self.include_order.clear()
        self.available_types.clear()
        
        def process_header(path: Path, visited: Set[Path]) -> List[Path]:
            if path in visited:
                return []  # Previeni cicli
                
            if path in self.include_order:
                return self.include_order[path]
                
            visited.add(path)
            source = self.source_files[path]
            order = []
            
            # Calcola i tipi richiesti
            required_types = self._check_type_dependencies(source)
            
            # Determina quali include forniscono i tipi necessari
            available = set()
            remaining_includes = set(source.includes)
            
            while required_types and remaining_includes:
                best_include = None
                best_types = set()
                
                for inc in remaining_includes:
                    if inc not in self.source_files:
                        continue
                        
                    # Calcola i tipi forniti da questo include
                    inc_types = self._calculate_available_types(inc)
                    needed_types = required_types & inc_types
                    
                    if needed_types and (not best_include or len(needed_types) > len(best_types)):
                        best_include = inc
                        best_types = needed_types
                
                if not best_include:
                    break
                    
                # Aggiungi l'include migliore all'ordine
                order.extend(process_header(best_include, visited.copy()))
                order.append(best_include)
                remaining_includes.remove(best_include)
                available.update(best_types)
                required_types -= best_types
            
            # Aggiungi gli include rimanenti
            for inc in remaining_includes:
                if inc in self.source_files:
                    order.extend(process_header(inc, visited.copy()))
                    order.append(inc)
            
            visited.remove(path)
            self.include_order[path] = order
            return order
        
        # Processa tutti gli header
        for path in self.source_files:
            if path not in self.include_order and self.source_files[path].is_header:
                process_header(path, set())
    
    def verify_includes(self) -> dict:
        """Verifica le relazioni di inclusione e identifica i problemi"""
        issues = {
            'missing_types': defaultdict(set),
            'circular_deps': [],
            'unnecessary_includes': defaultdict(set)
        }
        
        # Verifica i tipi mancanti
        for path, source in self.source_files.items():
            required_types = self._check_type_dependencies(source)
            available_types = self._calculate_available_types(path)
            
            missing = required_types - available_types
            if missing:
                issues['missing_types'][str(path)] = missing
        
        # Trova le dipendenze circolari
        issues['circular_deps'] = self._find_circular_deps()
        
        # Trova gli include non necessari
        for path, source in self.source_files.items():
            required_types = self._check_type_dependencies(source)
            
            for inc in source.includes:
                if inc not in self.source_files:
                    continue
                    
                inc_types = self._calculate_available_types(inc)
                if not (required_types & inc_types):
                    issues['unnecessary_includes'][str(path)].add(str(inc))
        
        return issues
    
    def analyze(self):
        """Main analysis workflow"""
        self._build_symbol_table()
        self._analyze_dependencies()
        self._resolve_include_order()  # Ora usa la nuova logica di risoluzione dei tipi
        
        # Calcola i tipi disponibili per tutti i file
        for path in self.source_files:
            self._calculate_available_types(path)

    def get_source_analysis(self) -> Dict[str, dict]:
        """
        Get comprehensive analysis for all source files including type information.
        """
        sources = {}
        
        for path, source in self.source_files.items():
            str_path = str(path)
            header_deps = self.header_deps.get(path)
            
            # Base source info
            source_info = {
                'path': str_path,
                'is_header': source.is_header,
                'symbols': {
                    'provided': [],
                    'required': [],
                    'types': {
                        'available': list(source.available_types),
                        'required': list(self._check_type_dependencies(source))
                    }
                },
                'includes': {
                    'optimal_order': [str(p) for p in self.get_include_order(path)],
                    'current': [str(p) for p in source.includes],
                    'direct': [],
                    'transitive': [],
                    'unnecessary': []
                },
                'dependencies': {
                    'dependent_files': [],
                    'dependency_chain': self._get_dependency_chain(path),
                    'type_dependencies': self._get_type_dependency_chain(path)
                },
                'analysis': {
                    'has_circular_deps': False,
                    'missing_symbols': [],
                    'missing_types': [],
                    'symbol_overlap': [],
                    'include_suggestions': []
                }
            }
            
            # Add symbol information
            if header_deps:
                # Provided symbols with details
                for symbol in header_deps.provided_symbols:
                    symbol_info = self._get_symbol_info(symbol, path)
                    source_info['symbols']['provided'].append(symbol_info)
                
                # Required symbols with details
                for symbol in header_deps.required_symbols:
                    symbol_info = self._get_symbol_info(symbol, path)
                    source_info['symbols']['required'].append(symbol_info)
                
                # Include relationships
                source_info['includes']['direct'] = [
                    str(p) for p in header_deps.direct_includes
                ]
                source_info['includes']['transitive'] = [
                    str(p) for p in header_deps.transitive_includes
                ]
                source_info['dependencies']['dependent_files'] = [
                    str(p) for p in header_deps.dependents
                ]
            
            # Add analysis information with type checks
            self._add_analysis_info(source_info, path)
            
            sources[str_path] = source_info
            
        return sources

    def _get_type_dependency_chain(self, path: Path) -> List[dict]:
        """Get dependency chain based on type requirements"""
        chain = []
        source = self.source_files[path]
        required_types = self._check_type_dependencies(source)
        
        for type_name in required_types:
            providers = []
            for inc_path in source.includes:
                if inc_path in self.source_files:
                    inc_types = self._calculate_available_types(inc_path)
                    if type_name in inc_types:
                        providers.append({
                            'file': str(inc_path),
                            'direct_provider': type_name in self.source_files[inc_path].available_types
                        })
            
            if providers:
                chain.append({
                    'type': type_name,
                    'providers': providers
                })
        
        return chain

    def _add_analysis_info(self, source_info: dict, path: Path):
        """Add analysis information including type analysis to source info"""
        # Existing checks (circular deps, etc.)
        super()._add_analysis_info(source_info, path)
        
        # Add type-specific analysis
        source = self.source_files[path]
        required_types = self._check_type_dependencies(source)
        available_types = self._calculate_available_types(path)
        
        # Find missing types
        missing_types = required_types - available_types
        if missing_types:
            source_info['analysis']['missing_types'] = list(missing_types)
        
        # Update include suggestions based on type dependencies
        suggestions = source_info['analysis']['include_suggestions']
        
        # Check for better include ordering based on types
        current_order = [str(p) for p in source.includes]
        optimal_order = [str(p) for p in self.get_include_order(path)]
        
        if current_order != optimal_order:
            suggestions.append({
                'type': 'reorder',
                'message': 'Consider reordering includes to resolve type dependencies properly',
                'current_order': current_order,
                'suggested_order': optimal_order,
                'affected_types': list(required_types)
            })
    
    def usage():
        project_paths = "c-project/"
        
        analyzer = SourceAnalyzer([project_paths])
        analyzer.analyze()
        
        #result = optimize_includes(analyzer.files)
        # Create resolver
        resolver = ImprovedIncludeResolver(analyzer.files)

        # Run analysis
        resolver.analyze()

        # Get comprehensive source analysis
        sources = resolver.get_source_analysis()

        # Verify includes
        issues = resolver.verify_includes()

        result = {}
        result['sources'] = sources 
        result['issues'] = issues
        return result