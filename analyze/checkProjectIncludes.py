import os
import subprocess
from typing import Dict, Set, List
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config
from pathlib import Path

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

class CIncludeAnalyzer:
    def __init__(self, project_path: str, excluded_paths: List[str] = None):
        self.project_path = Path(project_path)
        self.excluded_paths = [Path(p).resolve() for p in (excluded_paths or [])]
        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        self.index = Index.create()
        
        self.file_includes: Dict[str, Set[str]] = {}
        self.file_used_types: Dict[str, Set[str]] = {}
        self.header_types: Dict[str, Set[str]] = {}
    
    def should_exclude(self, path: Path) -> bool:
        """Verifica se un path deve essere escluso"""
        try:
            resolved_path = path.resolve()
            for excluded in self.excluded_paths:
                if str(resolved_path).startswith(str(excluded)):
                    return True
            return False
        except Exception:
            # In caso di errori nella risoluzione del path, non lo escludiamo
            return False

    def find_c_files(self) -> List[Path]:
        """
        Trova ricorsivamente tutti i file .c e .h nel progetto,
        escludendo i path specificati
        """
        c_files = []
        
        def is_hidden(path: Path) -> bool:
            """Verifica se un path è nascosto (inizia con .)"""
            return any(part.startswith('.') for part in path.parts)
        
        def recursive_find(directory: Path):
            try:
                for item in directory.iterdir():
                    # Salta file e directory nascosti
                    if is_hidden(item):
                        continue
                    
                    # Salta path esclusi
                    if self.should_exclude(item):
                        print(f"Escluso: {item}")
                        continue
                    
                    if item.is_file():
                        if item.suffix in ['.c', '.h', '.cpp', '.hpp']:
                            c_files.append(item)
                    elif item.is_dir():
                        recursive_find(item)
            except PermissionError:
                print(f"Permesso negato per la directory: {directory}")
            except Exception as e:
                print(f"Errore nell'accesso a {directory}: {e}")
        
        recursive_find(self.project_path)
        return c_files

    def get_c_files(self) -> List[str]:
        """Trova tutti i file .c e .h nel progetto"""
        return [str(f) for f in self.find_c_files()]

    def parse_file(self, file_path: str):
        """Analizza un singolo file"""
        try:
            tu = self.index.parse(file_path)
            if not tu:
                print(f"Errore nel parsing di {file_path}")
                return

            # Analizza gli include
            includes = set()
            for inc in tu.get_includes():
                includes.add(os.path.basename(inc.include.name))
            self.file_includes[file_path] = includes

            # Analizza i tipi usati
            used_types = set()
            self._analyze_types(tu.cursor, used_types)
            self.file_used_types[file_path] = used_types

            # Se è un header file, analizza i tipi definiti
            if file_path.endswith(('.h', '.hpp')):
                defined_types = set()
                self._analyze_defined_types(tu.cursor, defined_types)
                self.header_types[file_path] = defined_types

        except Exception as e:
            print(f"Errore nell'analisi di {file_path}: {e}")

    def _analyze_types(self, cursor, used_types: Set[str]):
        """Analizza ricorsivamente i tipi usati nel codice"""
        if cursor.kind in [CursorKind.TYPE_REF, CursorKind.DECL_REF_EXPR]:
            type_name = cursor.type.get_canonical().spelling
            if type_name:
                used_types.add(type_name)
        
        for child in cursor.get_children():
            self._analyze_types(child, used_types)

    def _analyze_defined_types(self, cursor, defined_types: Set[str]):
        """Analizza i tipi definiti in un header"""
        if cursor.kind in [CursorKind.TYPEDEF_DECL, CursorKind.STRUCT_DECL, 
                         CursorKind.ENUM_DECL, CursorKind.UNION_DECL]:
            if cursor.spelling:
                defined_types.add(cursor.spelling)
        
        for child in cursor.get_children():
            self._analyze_defined_types(child, defined_types)

    def analyze_project(self):
        """Analizza l'intero progetto"""
        c_files = self.get_c_files()
        total_files = len(c_files)
        print(f"Trovati {total_files} file da analizzare")
        
        for idx, file in enumerate(c_files, 1):
            print(f"[{idx}/{total_files}] Analisi di {file}")
            self.parse_file(file)

    def find_necessary_includes(self) -> Dict[str, Dict[str, bool]]:
        """Determina quali include sono necessari e quali superflui"""
        results = {}
        
        for file_path, includes in self.file_includes.items():
            results[file_path] = {}
            used_types = self.file_used_types.get(file_path, set())
            
            for include in includes:
                include_path = None
                for header in self.header_types:
                    if os.path.basename(header) == include:
                        include_path = header
                        break
                
                if include_path:
                    # Un include è necessario se definisce almeno un tipo usato nel file
                    defined_types = self.header_types.get(include_path, set())
                    is_necessary = any(used_type in defined_types for used_type in used_types)
                    results[file_path][include] = is_necessary
                else:
                    # Se non troviamo l'header nel progetto, lo consideriamo necessario
                    # (potrebbe essere un header di sistema)
                    results[file_path][include] = True
                    
        return results

def main():
    project_path = "../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3" #input("Inserisci il percorso del progetto C da analizzare: ")
    project_path = os.path.abspath(project_path)

    # Chiedi all'utente se vuole escludere dei path
    excluded_paths = ["build/"]

    while False:
        path = project_path # input("Inserisci un path da escludere (premi Invio per continuare): ").strip()
        if not path:
            break
        excluded_paths.append(path)
    
    analyzer = CIncludeAnalyzer(project_path, excluded_paths)
    
    print("\nAvvio analisi del progetto...")
    analyzer.analyze_project()
    
    print("\nAnalisi degli #include:")
    results = analyzer.find_necessary_includes()
    
    for file_path, includes in results.items():
        print(f"\nFile: {file_path}")
        print("Include necessari:")
        necessary = [inc for inc, nec in includes.items() if nec]
        if necessary:
            for include in sorted(necessary):
                print(f"  ✓ {include}")
        else:
            print("  (nessuno)")
            
        print("Include potenzialmente rimuovibili:")
        removable = [inc for inc, nec in includes.items() if not nec]
        if removable:
            for include in sorted(removable):
                print(f"  ✗ {include}")
        else:
            print("  (nessuno)")

if __name__ == "__main__":
    main()

#pip install clang