import os
import subprocess
from typing import Dict, Set, List, Optional, Tuple, DefaultDict
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

def setup_libclang():
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
                
        print("ERRORE: libclang non trovato. Assicurati di avere installato LLVM:")
        print("brew install llvm")
        return False
    except subprocess.CalledProcessError:
        print("ERRORE: Homebrew non trovato. Installa Homebrew da https://brew.sh")
        return False

@dataclass
class TypeInfo:
    """Informazioni su un tipo"""
    name: str
    defined_in: str  # nome del file che definisce il tipo
    used_in: Set[str] = field(default_factory=set)  # nomi dei file che usano il tipo
    included_via: Set[str] = field(default_factory=set)  # file attraverso cui il tipo è disponibile

@dataclass
class CSourceFile:
    """Rappresenta un file sorgente nel progetto"""
    path: Path
    name: str = ""
    base_name: str = ""
    is_header: bool = False
    
    # Tipi e dipendenze
    defined_types: Set[str] = field(default_factory=set)
    used_types: Set[str] = field(default_factory=set)
    
    # Include diretti
    direct_includes: Set[str] = field(default_factory=set)  # rinominato da direct_includes
    
    # Include necessari calcolati
    required_includes: Set[str] = field(default_factory=set)
    
    # Dipendenze transitive (tutti i tipi disponibili tramite include)
    available_types: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        self.name = self.path.name
        self.base_name = self.path.stem
        self.is_header = self.path.suffix in ['.h', '.hpp']

class DependencyGraph:
    """Gestisce il grafo delle dipendenze tra file"""
    def __init__(self):
        self.type_info: Dict[str, TypeInfo] = {}  # tipo -> info sul tipo
        self.file_dependencies: DefaultDict[str, Set[str]] = defaultdict(set)  # file -> dipendenze
        self.reverse_dependencies: DefaultDict[str, Set[str]] = defaultdict(set)  # file -> chi dipende da questo
        self.processed_order: List[str] = []  # ordine di processamento dei file
    
    def add_type(self, type_name: str, defined_in: str):
        """Aggiunge un tipo al grafo"""
        if type_name not in self.type_info:
            self.type_info[type_name] = TypeInfo(type_name, defined_in)
    
    def add_type_usage(self, type_name: str, used_in: str):
        """Registra l'uso di un tipo in un file"""
        if type_name in self.type_info:
            self.type_info[type_name].used_in.add(used_in)
    
    def add_include(self, file: str, includes: str):
        """Aggiunge una relazione di inclusione al grafo"""
        self.file_dependencies[file].add(includes)
        self.reverse_dependencies[includes].add(file)
    
    def get_required_includes(self, file: str) -> Set[str]:
        """Determina gli include necessari per un file"""
        required = set()
        
        # Se il file è nella lista dei processati, usa quella sequenza
        if file in self.processed_order:
            idx = self.processed_order.index(file)
            available_types = set()
            
            # Analizza gli include nell'ordine di processamento
            for processed_file in self.processed_order[:idx]:
                if processed_file in self.file_dependencies[file]:
                    file_types = {t.name for t in self.type_info.values() 
                                if t.defined_in == processed_file}
                    available_types.update(file_types)
                    if file_types:
                        required.add(processed_file)
        
        return required

class ProjectAnalyzer:
    def __init__(self, project_path: str, excluded_paths: List[str] = None):
        self.project_path = Path(project_path)
        self.excluded_paths = [Path(p).resolve() for p in (excluded_paths or [])]
        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        self.index = Index.create()
        
        self.files: Dict[str, CSourceFile] = {}
        self.dependency_graph = DependencyGraph()
        
        # Cache per le corrispondenze header/source
        self.header_to_source: Dict[str, str] = {}
        self.source_to_header: Dict[str, str] = {}

    def find_source_files(self) -> Tuple[List[Path], List[Path]]:
        """Trova ricorsivamente i file sorgente e header nel progetto"""
        headers = []
        sources = []
        
        def is_hidden(path: Path) -> bool:
            return any(part.startswith('.') for part in path.parts)
        
        def recursive_find(directory: Path):
            try:
                for item in directory.iterdir():
                    if is_hidden(item) or self.should_exclude(item):
                        continue
                    
                    if item.is_file():
                        if item.suffix in ['.h', '.hpp']:
                            headers.append(item)
                        elif item.suffix in ['.c', '.cpp']:
                            sources.append(item)
                    elif item.is_dir():
                        recursive_find(item)
            except Exception as e:
                print(f"Errore nell'accesso a {directory}: {e}")
        
        recursive_find(self.project_path)
        return sorted(headers), sorted(sources)
    
    def _analyze_includes(self, tu, source_file: CSourceFile):
        """Analizza gli include nel file"""
        for inc in tu.get_includes():
            include_name = os.path.basename(inc.include.name)
            if not include_name.endswith(('.c', '.cpp')):
                source_file.direct_includes.add(include_name)

    def _analyze_types(self, cursor, source_file: CSourceFile):
        """Analizza ricorsivamente i tipi nel file"""
        if cursor.kind in [CursorKind.TYPEDEF_DECL, CursorKind.STRUCT_DECL, 
                        CursorKind.ENUM_DECL, CursorKind.UNION_DECL]:
            if cursor.spelling:
                source_file.defined_types.add(cursor.spelling)
        
        elif cursor.kind == CursorKind.TYPE_REF:
            type_name = cursor.type.get_canonical().spelling
            if type_name:
                source_file.used_types.add(type_name)
        
        for child in cursor.get_children():
            self._analyze_types(child, source_file)

    def find_and_analyze_files(self):
        """Trova e analizza tutti i file del progetto"""
        # Prima trova tutti i file
        headers, sources = self.find_source_files()
        
        # Mappa le corrispondenze header/source
        self._map_header_source_pairs(headers, sources)
        
        # Analizza prima gli header
        for header in headers:
            self._analyze_file(header)
        
        # Poi i source files
        for source in sources:
            self._analyze_file(source)
        
        # Risolvi le dipendenze
        self._resolve_all_dependencies()
    
    def _map_header_source_pairs(self, headers: List[Path], sources: List[Path]):
        """Mappa le corrispondenze tra header e source files"""
        header_dict = {h.stem: h.name for h in headers}
        source_dict = {s.stem: s.name for s in sources}
        
        for stem in header_dict:
            if stem in source_dict:
                self.header_to_source[header_dict[stem]] = source_dict[stem]
                self.source_to_header[source_dict[stem]] = header_dict[stem]
    
    def _analyze_file(self, file_path: Path):
        """Analizza un singolo file"""
        try:
            source_file = CSourceFile(path=file_path)
            
            # Analizza il file con clang
            tu = self.index.parse(str(file_path))
            if not tu:
                print(f"Errore nel parsing di {file_path}")
                return
            
            # Analizza include e tipi
            self._analyze_includes(tu, source_file)
            self._analyze_types(tu.cursor, source_file)
            
            # Aggiorna il grafo delle dipendenze
            for type_name in source_file.defined_types:
                self.dependency_graph.add_type(type_name, source_file.name)
            
            for type_name in source_file.used_types:
                self.dependency_graph.add_type_usage(type_name, source_file.name)
            
            for include in source_file.direct_includes:
                self.dependency_graph.add_include(source_file.name, include)
            
            self.files[source_file.name] = source_file
            
        except Exception as e:
            print(f"Errore nell'analisi di {file_path}: {e}")
    
    def _resolve_all_dependencies(self):
        """Risolve tutte le dipendenze dei file"""
        # Prima processa gli header
        for file_name, file in self.files.items():
            if file.is_header:
                self._resolve_file_dependencies(file)
        
        # Poi i source files
        for file_name, file in self.files.items():
            if not file.is_header:
                if file.name in self.source_to_header:
                    # Se ha un header, include solo quello
                    file.required_includes = {self.source_to_header[file.name]}
                else:
                    # Altrimenti risolvi le dipendenze normalmente
                    self._resolve_file_dependencies(file)
    
    def _resolve_file_dependencies(self, file: CSourceFile):
        """Risolve le dipendenze per un singolo file"""
        required = set()
        available_types = set()
        
        # Prima aggiungi gli include diretti necessari
        for include in file.direct_includes:
            if include in self.files:
                included_file = self.files[include]
                if any(t in file.used_types for t in included_file.defined_types):
                    required.add(include)
                    available_types.update(included_file.defined_types)
        
        # Poi trova gli include aggiuntivi necessari
        for type_name in file.used_types:
            if type_name not in available_types:
                type_info = self.dependency_graph.type_info.get(type_name)
                if type_info and type_info.defined_in != file.name:
                    required.add(type_info.defined_in)
        
        file.required_includes = {inc for inc in required 
                                if not inc.endswith(('.c', '.cpp'))}
    
    def print_report(self):
        """Stampa il report delle dipendenze"""
        for file_name, file in sorted(self.files.items()):
            print(f"\nFile: {file.path}")
            
            # Stampa gli include necessari
            print("Include necessari:")
            if file.required_includes:
                for include in sorted(file.required_includes):
                    print(f"#include \"{include}\"")
            else:
                print("  (nessuno)")
            
            # Stampa gli include rimuovibili (usa direct_includes invece di direct_includes)
            removable = file.direct_includes - file.required_includes
            removable = {inc for inc in removable 
                        if not inc.endswith(('.c', '.cpp'))}
            if removable:
                print("\nInclude potenzialmente rimuovibili:")
                for include in sorted(removable):
                    print(f"  ✗ {include}")

    def should_exclude(self, path: Path) -> bool:
        """Verifica se un path deve essere escluso"""
        try:
            resolved_path = path.resolve()
            return any(str(resolved_path).startswith(str(excluded)) 
                      for excluded in self.excluded_paths)
        except Exception:
            return False

    def find_source_files(self) -> Tuple[List[Path], List[Path]]:
        """Trova ricorsivamente i file sorgente e header nel progetto"""
        headers = []
        sources = []
        
        def is_hidden(path: Path) -> bool:
            return any(part.startswith('.') for part in path.parts)
        
        def recursive_find(directory: Path):
            try:
                for item in directory.iterdir():
                    if is_hidden(item) or self.should_exclude(item):
                        continue
                    
                    if item.is_file():
                        if item.suffix in ['.h', '.hpp']:
                            headers.append(item)
                        elif item.suffix in ['.c', '.cpp']:
                            sources.append(item)
                    elif item.is_dir():
                        recursive_find(item)
            except Exception as e:
                print(f"Errore nell'accesso a {directory}: {e}")
        
        recursive_find(self.project_path)
        return sorted(headers), sorted(sources)

    def link_corresponding_files(self):
        """Collega i file .c ai loro .h corrispondenti e viceversa"""
        for source_name, source_file in self.sources.items():
            header_name = f"{source_file.base_name}.h"
            if header_name in self.headers:
                source_file.corresponding_file = self.headers[header_name]
                self.headers[header_name].corresponding_file = source_file

    def analyze_file(self, file_path: Path) -> Optional[CSourceFile]:
        """Analizza un singolo file"""
        try:
            source_file = CSourceFile(path=file_path)
            tu = self.index.parse(str(file_path))
            
            if not tu:
                print(f"Errore nel parsing di {file_path}")
                return None

            self._analyze_includes(tu, source_file)
            self._analyze_cursor(tu.cursor, source_file)
            
            source_file.analyzed = True
            return source_file

        except Exception as e:
            print(f"Errore nell'analisi di {file_path}: {e}")
            return None

    def _analyze_includes(self, tu, source_file: CSourceFile):
        """Analizza gli include nel file"""
        for inc in tu.get_includes():
            include_name = os.path.basename(inc.include.name)
            # Ignora inclusioni di file .c
            if not include_name.endswith(('.c', '.cpp')):
                source_file.direct_includes.add(include_name)

    def _analyze_cursor(self, cursor, source_file: CSourceFile):
        """Analizza ricorsivamente il contenuto del file"""
        if cursor.kind == CursorKind.TYPEDEF_DECL:
            if cursor.spelling:
                source_file.defined_types.add(cursor.spelling)
                self.type_definitions[cursor.spelling] = source_file
        
        elif cursor.kind in [CursorKind.STRUCT_DECL, CursorKind.ENUM_DECL, CursorKind.UNION_DECL]:
            if cursor.spelling:
                source_file.defined_types.add(cursor.spelling)
                self.type_definitions[cursor.spelling] = source_file
        
        elif cursor.kind == CursorKind.FUNCTION_DECL:
            if cursor.spelling:
                source_file.functions_declared.add(cursor.spelling)
                self.function_declarations[cursor.spelling] = source_file
        
        elif cursor.kind == CursorKind.VAR_DECL:
            if cursor.spelling:
                source_file.variables_declared.add(cursor.spelling)
                self.variable_declarations[cursor.spelling] = source_file
        
        elif cursor.kind == CursorKind.DECL_REF_EXPR:
            if cursor.spelling:
                if cursor.type.kind == TypeKind.FUNCTIONPROTO:
                    source_file.functions_used.add(cursor.spelling)
                else:
                    source_file.variables_used.add(cursor.spelling)
        
        elif cursor.kind == CursorKind.TYPE_REF:
            type_name = cursor.type.get_canonical().spelling
            if type_name:
                source_file.used_types.add(type_name)

        for child in cursor.get_children():
            self._analyze_cursor(child, source_file)

    def _determine_required_includes(self, source_file: CSourceFile):
        """Determina gli include necessari per un file"""
        # Se è un file .c con un .h corrispondente, manteniamo solo l'include del suo header
        if not source_file.is_header and source_file.corresponding_file:
            source_file.required_includes = {source_file.corresponding_file.name}
            return

        required = set()
        
        # Per header files e source files senza header corrispondente
        # Aggiungi tutte le dipendenze basate sui tipi
        for type_name in source_file.used_types:
            if type_name in self.type_definitions:
                defining_file = self.type_definitions[type_name]
                if defining_file.name != source_file.name:  # Evita auto-inclusione
                    if defining_file.is_header:  # Includi solo header files
                        required.add(defining_file.name)
                    elif defining_file.corresponding_file:  # Se il tipo è definito in un .c che ha un .h
                        required.add(defining_file.corresponding_file.name)

        # Aggiungi le dipendenze basate sulle funzioni
        for func_name in source_file.functions_used:
            if func_name in self.function_declarations:
                declaring_file = self.function_declarations[func_name]
                if declaring_file.name != source_file.name:
                    if declaring_file.is_header:
                        required.add(declaring_file.name)
                    elif declaring_file.corresponding_file:
                        required.add(declaring_file.corresponding_file.name)

        # Aggiungi le dipendenze basate sulle variabili
        for var_name in source_file.variables_used:
            if var_name in self.variable_declarations:
                declaring_file = self.variable_declarations[var_name]
                if declaring_file.name != source_file.name:
                    if declaring_file.is_header:
                        required.add(declaring_file.name)
                    elif declaring_file.corresponding_file:
                        required.add(declaring_file.corresponding_file.name)

        # Aggiungi gli include transitivi dai file inclusi
        for include in source_file.direct_includes:
            if include in self.headers:
                header_file = self.headers[include]
                if header_file.required_includes:
                    required.update(header_file.required_includes)

        # Rimuovi file .c e auto-inclusioni
        filtered = {inc for inc in required 
                if not inc.endswith(('.c', '.cpp')) and inc != source_file.name}

        # Aggiungi tutti gli include espliciti che non sono file .c
        filtered.update({inc for inc in source_file.direct_includes 
                        if not inc.endswith(('.c', '.cpp'))})

        source_file.required_includes = filtered

    
    def analyze_project(self):
        """Analizza l'intero progetto"""
        headers, sources = self.find_source_files()
        total_files = len(headers) + len(sources)
        print(f"Trovati {total_files} file da analizzare ({len(headers)} headers, {len(sources)} sources)")
        
        # Analizza prima gli header
        print("\nAnalisi degli header files...")
        for file_path in headers:
            print(f"Analisi di {file_path}")
            source_file = self.analyze_file(file_path)
            if source_file:
                self.headers[source_file.name] = source_file
        
        # Poi analizza i sorgenti
        print("\nAnalisi dei file sorgente...")
        for file_path in sources:
            print(f"Analisi di {file_path}")
            source_file = self.analyze_file(file_path)
            if source_file:
                self.sources[source_file.name] = source_file
        
        # Collega i file corrispondenti
        self.link_corresponding_files()
        
        # Determina le dipendenze necessarie
        for source_file in [*self.headers.values(), *self.sources.values()]:
            self._determine_required_includes(source_file)


def main():
    project_path = "../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3"
    project_path = os.path.abspath(project_path)
    
    excluded_paths = ["build/"]
    analyzer = ProjectAnalyzer(project_path, excluded_paths)
    
    print("Avvio analisi del progetto...")
    analyzer.find_and_analyze_files()  # invece di analyze_project()
    
    print("\nAnalisi degli #include:")
    analyzer.print_report()

if __name__ == "__main__":
    main()

#pip install clang
# clear & python3 checkProjectIncludes.py