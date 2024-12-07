
import os
import subprocess
from typing import Dict, Set, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config

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

@dataclass
class TypeInfo:
    """Informazioni su un tipo"""
    name: str
    defined_in: str  # Nome del file che definisce il tipo
    used_in: Set[str] = field(default_factory=set)  # File che usano il tipo
    included_via: Set[str] = field(default_factory=set)  # File attraverso cui è disponibile

@dataclass
class CSourceFile:
    """Rappresenta un file sorgente C/C++"""
    path: Path
    is_header: bool = False
    corresponding_file: Optional['CSourceFile'] = None
    
    # Set per tracciare tipi e simboli
    defined_types: Set[str] = field(default_factory=set)
    used_types: Set[str] = field(default_factory=set)
    functions_declared: Set[str] = field(default_factory=set)
    functions_used: Set[str] = field(default_factory=set)
    variables_declared: Set[str] = field(default_factory=set)
    variables_used: Set[str] = field(default_factory=set)
    
    # Include diretti e calcolati
    direct_includes: Set[str] = field(default_factory=set)
    required_includes: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        self.name = self.path.name
        self.base_name = self.path.stem
        self.is_header = self.path.suffix in ['.h', '.hpp']

class ProjectAnalyzer:
    def __init__(self, project_path: str, excluded_paths: List[str] = None):
        self.project_path = Path(project_path)
        self.excluded_paths = [Path(p).resolve() for p in (excluded_paths or [])]
        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        
        self.index = Index.create()
        self.files: Dict[str, CSourceFile] = {}
        self.headers: Dict[str, CSourceFile] = {}
        self.sources: Dict[str, CSourceFile] = {}
        
        # Cache per lookup veloce
        self.type_definitions: Dict[str, CSourceFile] = {}
        self.function_declarations: Dict[str, CSourceFile] = {}
        self.variable_declarations: Dict[str, CSourceFile] = {}

    def should_exclude(self, path: Path) -> bool:
        """Verifica se un path deve essere escluso"""
        try:
            resolved_path = path.resolve()
            return any(str(resolved_path).startswith(str(excluded)) 
                      for excluded in self.excluded_paths)
        except Exception:
            return False

    def find_source_files(self) -> Tuple[List[Path], List[Path]]:
        """Trova tutti i file sorgente nel progetto"""
        headers, sources = [], []
        
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

    def _map_corresponding_files(self):
        """Mappa le corrispondenze tra file .h e .c"""
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

            # Analizza gli include
            for inc in tu.get_includes():
                include_name = os.path.basename(inc.include.name)
                if not include_name.endswith(('.c', '.cpp')):
                    source_file.direct_includes.add(include_name)

            # Analizza il contenuto
            self._analyze_symbols(tu.cursor, source_file)
            
            return source_file

        except Exception as e:
            print(f"Errore nell'analisi di {file_path}: {e}")
            return None

    def _analyze_symbols(self, cursor, source_file: CSourceFile):
        """Analizza i simboli nel file"""
        if cursor.kind in [CursorKind.TYPEDEF_DECL, CursorKind.STRUCT_DECL, 
                         CursorKind.ENUM_DECL, CursorKind.UNION_DECL]:
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
            self._analyze_symbols(child, source_file)

    def analyze_project(self):
        """Analizza l'intero progetto"""
        # Trova tutti i file
        headers, sources = self.find_source_files()
        print(f"Trovati {len(headers)} header e {len(sources)} source files")
        
        # Analizza gli header
        print("\nAnalisi degli header files...")
        for header in headers:
            print(f"Analisi di {header}")
            if result := self.analyze_file(header):
                self.headers[result.name] = result
                self.files[result.name] = result
        
        # Analizza i source files
        print("\nAnalisi dei source files...")
        for source in sources:
            print(f"Analisi di {source}")
            if result := self.analyze_file(source):
                self.sources[result.name] = result
                self.files[result.name] = result
        
        # Mappa le corrispondenze
        self._map_corresponding_files()
        
        # Calcola le dipendenze
        self._calculate_all_dependencies()

    def _calculate_all_dependencies(self):
        """Calcola le dipendenze per tutti i file"""
        # Prima gli header
        for file in self.headers.values():
            self._calculate_file_dependencies(file)
        
        # Poi i source files
        for file in self.sources.values():
            if file.corresponding_file:
                # Se ha un header corrispondente, include solo quello
                file.required_includes = {file.corresponding_file.name}
            else:
                self._calculate_file_dependencies(file)

    def _calculate_file_dependencies(self, file: CSourceFile):
        """Calcola le dipendenze per un singolo file"""
        if not file.is_header and file.corresponding_file:
            return  # Skip se è un .c con header corrispondente
        
        required = set()
        
        # Funzione helper per aggiungere una dipendenza
        def add_dependency(dep_file: CSourceFile):
            if dep_file.is_header:
                required.add(dep_file.name)
            elif dep_file.corresponding_file:
                required.add(dep_file.corresponding_file.name)
        
        # Verifica dipendenze per tipi
        for type_name in file.used_types:
            if type_name in self.type_definitions:
                def_file = self.type_definitions[type_name]
                if def_file.name != file.name:
                    add_dependency(def_file)
        
        # Verifica dipendenze per funzioni
        for func_name in file.functions_used:
            if func_name in self.function_declarations:
                decl_file = self.function_declarations[func_name]
                if decl_file.name != file.name:
                    add_dependency(decl_file)
        
        # Verifica dipendenze per variabili
        for var_name in file.variables_used:
            if var_name in self.variable_declarations:
                decl_file = self.variable_declarations[var_name]
                if decl_file.name != file.name:
                    add_dependency(decl_file)
        
        # Filtra e aggiorna le dipendenze
        file.required_includes = {inc for inc in required 
                                if not inc.endswith(('.c', '.cpp'))
                                and inc != file.name}

    def print_report(self):
        """Stampa il report delle dipendenze"""
        for file_name, file in sorted(self.files.items()):
            print(f"\nFile: {file.path}")
            
            # Stampa include necessari
            if file.required_includes:
                print("Include necessari:")
                for include in sorted(file.required_includes):
                    print(f"#include \"{include}\"")
            
            # Stampa include rimuovibili
            removable = file.direct_includes - file.required_includes
            removable = {inc for inc in removable 
                        if not inc.endswith(('.c', '.cpp'))}
            if removable:
                print("\nInclude potenzialmente rimuovibili:")
                for include in sorted(removable):
                    print(f"  ✗ {include}")

def main():
    project_path = "../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3"
    project_path = os.path.abspath(project_path)
    excluded_paths = ["build/"]
    
    analyzer = ProjectAnalyzer(project_path, excluded_paths)
    print("Avvio analisi del progetto...")
    analyzer.analyze_project()
    print("\nAnalisi degli #include:")
    analyzer.print_report()

if __name__ == "__main__":
    main()
