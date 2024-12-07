import os
import subprocess
from typing import Dict, Set, List, Optional, Tuple
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
class CSourceFile:
    """Rappresenta un file sorgente C o header"""
    path: Path
    explicit_includes: Set[str] = field(default_factory=set)
    used_types: Set[str] = field(default_factory=set)
    defined_types: Set[str] = field(default_factory=set)
    functions_declared: Set[str] = field(default_factory=set)
    functions_used: Set[str] = field(default_factory=set)
    variables_declared: Set[str] = field(default_factory=set)
    variables_used: Set[str] = field(default_factory=set)
    required_includes: Set[str] = field(default_factory=set)
    name: str = ""
    base_name: str = ""
    is_header: bool = False
    corresponding_file: Optional['CSourceFile'] = None
    analyzed: bool = False

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
        
        # Dizionari separati per header e source files
        self.headers: Dict[str, CSourceFile] = {}
        self.sources: Dict[str, CSourceFile] = {}
        
        # Mapping tra tipi/funzioni/variabili e i file che li definiscono
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
                source_file.explicit_includes.add(include_name)

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
        for include in source_file.explicit_includes:
            if include in self.headers:
                header_file = self.headers[include]
                if header_file.required_includes:
                    required.update(header_file.required_includes)

        # Rimuovi file .c e auto-inclusioni
        filtered = {inc for inc in required 
                if not inc.endswith(('.c', '.cpp')) and inc != source_file.name}

        # Aggiungi tutti gli include espliciti che non sono file .c
        filtered.update({inc for inc in source_file.explicit_includes 
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

    def print_report(self):
        """Stampa il report in formato personalizzato"""
        all_files = {**self.headers, **self.sources}
        
        for file_name, source_file in sorted(all_files.items()):
            print(f"\nFile: {source_file.path}")
            
            # Se è un file .c con un .h corrispondente, mostra solo l'include del suo header
            if not source_file.is_header and source_file.corresponding_file:
                print("Include necessari:")
                print(f"#include \"{source_file.corresponding_file.name}\"")
                continue
            
            # Per tutti gli altri file, mostra sempre gli include esistenti
            print("Include necessari:")
            all_includes = source_file.explicit_includes | source_file.required_includes
            if all_includes:
                for include in sorted(all_includes):
                    if not include.endswith(('.c', '.cpp')):  # Escludiamo sempre i .c
                        print(f"#include \"{include}\"")
            else:
                print("  (nessuno)")
            
            # Mostra gli include rimuovibili solo se ce ne sono
            removable = source_file.explicit_includes - source_file.required_includes
            if removable:
                print("\nInclude potenzialmente rimuovibili:")
                for include in sorted(removable):
                    if not include.endswith(('.c', '.cpp')):  # Escludiamo sempre i .c
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

#pip install clang
# clear & python3 checkProjectIncludes.py