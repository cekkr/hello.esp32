import os
from typing import Dict, Set, List, Generator
import clang.cindex
from dataclasses import dataclass, field  
from pathlib import Path
import networkx as nx
import platform
import subprocess

@dataclass
class TypeInfo:
    name: str
    file_path: str
    line_number: int
    used_in: str
    dependencies: Set[str] = field(default_factory=set)  # Inizializzazione corretta

    def add_dependency(self, dep: str):
        """Aggiunge una dipendenza al tipo."""
        if self.dependencies is None:
            self.dependencies = set()
        self.dependencies.add(dep)

def find_libclang():
    """Trova il percorso di libclang basato sul sistema operativo."""
    if platform.system() == "Darwin":  # macOS
        try:
            # Usa xcrun per trovare il percorso di clang
            result = subprocess.run(
                ["xcrun", "--find", "clang"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                clang_path = result.stdout.strip()
                # Il file dylib si trova tipicamente nella directory parent
                lib_path = Path(clang_path).parent.parent / "lib" / "libclang.dylib"
                if lib_path.exists():
                    return str(lib_path)
                
            # Percorsi alternativi comuni su macOS
            common_paths = [
                "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib",
                "/Library/Developer/CommandLineTools/usr/lib/libclang.dylib",
            ]
            for path in common_paths:
                if Path(path).exists():
                    return path
                    
        except subprocess.SubprocessError:
            pass
            
    elif platform.system() == "Linux":
        common_paths = [
            "/usr/lib/llvm-14/lib/libclang.so.1",
            "/usr/lib/x86_64-linux-gnu/libclang-14.so.1",
            "/usr/lib/libclang.so",
        ]
        for path in common_paths:
            if Path(path).exists():
                return path
                
    raise RuntimeError("Non è stato possibile trovare libclang nel sistema")

class HeaderDependencyAnalyzer:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.type_declarations: Dict[str, TypeInfo] = {}
        self.includes: Dict[str, Set[str]] = {}
        self.dependency_graph = nx.DiGraph()
        
        # Inizializza libclang con il percorso corretto
        libclang_path = find_libclang()
        clang.cindex.Config.set_library_file(libclang_path)
        self.index = clang.cindex.Index.create()

    def analyze_file(self, file_path: Path):
        try:
            # Aggiungi percorsi di include specifici per wasm3
            include_paths = [
                '-I' + str(self.project_path),
                '-I' + str(self.project_path / 'components'),
                '-I/Users/$USER/esp/esp-idf/components',
                '-I' + str(Path.home() / 'esp/esp-idf/components'),
                # Aggiungi percorsi specifici per wasm3
                '-I' + str(self.project_path / 'components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3'),
                '-I' + str(self.project_path / 'components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi'),
            ]
            
            tu = self.index.parse(
                str(file_path),
                args=['-x', 'c++'] + include_paths
            )
            
            if not tu:
                print(f"Errore: Impossibile parsare {file_path}")
                return

            self.analyze_declarations(tu.cursor, str(file_path))
            self.analyze_includes(file_path)
            
        except Exception as e:
            print(f"Errore dettagliato nell'analisi di {file_path}: {str(e)}")
            raise

    def analyze_declarations(self, cursor: clang.cindex.Cursor, file_path: str):
        """Analizza le dichiarazioni nel file con gestione migliorata degli errori."""
        try:
            for node in cursor.walk_preorder():
                if node.location.file and str(node.location.file) == file_path:
                    if node.kind in [
                        clang.cindex.CursorKind.STRUCT_DECL,
                        clang.cindex.CursorKind.CLASS_DECL,
                        clang.cindex.CursorKind.TYPEDEF_DECL,
                        clang.cindex.CursorKind.ENUM_DECL
                    ]:
                        # Analizza dipendenze del tipo corrente
                        dependencies = self._analyze_type_dependencies(node)
                        
                        type_info = TypeInfo(
                            name=node.spelling,
                            file_path=file_path,
                            line_number=node.location.line,
                            used_in=file_path,
                            dependencies=dependencies
                        )

                        # Poi analizza e aggiungi le dipendenze
                        dependencies = self._analyze_type_dependencies(node)
                        for dep in dependencies:
                            type_info.add_dependency(dep)

                        self.type_declarations[node.spelling] = type_info
                        
        except Exception as e:
            print(f"Errore nell'analisi delle dichiarazioni in {file_path}: {str(e)}")
            raise

    def _analyze_type_dependencies(self, node: clang.cindex.Cursor) -> Set[str]:
        """Analizza le dipendenze di un tipo specifico."""
        dependencies = set()
        try:
            for child in node.walk_preorder():
                if child.kind in [
                    clang.cindex.CursorKind.TYPE_REF,
                    clang.cindex.CursorKind.DECL_REF_EXPR
                ]:
                    referenced_type = child.spelling
                    if referenced_type and referenced_type != node.spelling:
                        dependencies.add(referenced_type)
                        
        except Exception as e:
            print(f"Errore nell'analisi delle dipendenze per {node.spelling}: {str(e)}")
            
        return dependencies

    def analyze_includes(self, file_path: Path):
        includes = set()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('#include'):
                    include_path = line.split('"')[1] if '"' in line else line.split('<')[1].split('>')[0]
                    includes.add(include_path)
                    
        self.includes[str(file_path)] = includes
        
        for include in includes:
            include_full_path = self.resolve_include_path(include, file_path)
            if include_full_path:
                self.dependency_graph.add_edge(str(file_path), str(include_full_path))

    def resolve_include_path(self, include_path: str, source_file: Path) -> Path:
        candidate = source_file.parent / include_path
        if candidate.exists():
            return candidate
            
        search_paths = [
            self.project_path,
            self.project_path / 'components',
            Path.home() / 'esp/esp-idf/components'
        ]
        
        for search_path in search_paths:
            candidate = search_path / include_path
            if candidate.exists():
                return candidate
        
        return None

    def find_source_files(self, start_path: Path) -> Generator[Path, None, None]:
        """
        Trova tutti i file sorgente in modo ricorsivo con debug avanzato.
        """
        source_extensions = {'.h', '.hpp', '.c', '.cpp', '.cxx', '.cc'}
        ignored_dirs = {
            'build', '.git', '.svn', '.hg',
            'node_modules', 'venv', 'env',
            '__pycache__', '.pytest_cache',
            '.vscode', '.idea', '.vs'
        }
        
        def debug_directory_structure(path: Path, level=0):
            """Helper function per stampare la struttura delle directory"""
            indent = "  " * level
            print(f"{indent}📁 {path.name}/")
            try:
                for item in path.iterdir():
                    if item.is_dir() and item.name not in ignored_dirs:
                        debug_directory_structure(item, level + 1)
                    elif item.is_file() and item.suffix.lower() in source_extensions:
                        print(f"{indent}  📄 {item.name}")
            except PermissionError as e:
                print(f"{indent}  ⚠️ Errore permessi: {e}")
        
        # Debug iniziale: mostra la struttura completa
        print("\n=== STRUTTURA DIRECTORY DEL PROGETTO ===")
        debug_directory_structure(start_path)
        print("\n=== INIZIO SCANSIONE FILE ===")
        
        start_path = start_path.absolute()
        
        def scan_directory(current_path: Path) -> Generator[Path, None, None]:
            """Funzione ricorsiva per scansionare le directory"""
            try:
                for item in current_path.iterdir():
                    if item.is_dir() and item.name not in ignored_dirs:
                        print(f"Entrando nella directory: {item}")
                        yield from scan_directory(item)
                    elif item.is_file() and item.suffix.lower() in source_extensions:
                        print(f"File trovato: {item}")
                        yield item
            except PermissionError as e:
                print(f"⚠️ Errore permessi in {current_path}: {e}")
        
        # Verifica esplicita per wasm3
        wasm3_dir = start_path / 'wasm3'
        if wasm3_dir.exists() and wasm3_dir.is_dir():
            print(f"\n=== ANALISI SPECIFICA DIRECTORY WASM3 ===")
            print(f"Directory wasm3 trovata in: {wasm3_dir}")
            try:
                wasm3_files = list(wasm3_dir.rglob('*'))
                print(f"Contenuto directory wasm3:")
                for f in wasm3_files:
                    if f.is_file() and f.suffix.lower() in source_extensions:
                        print(f"📄 {f.relative_to(wasm3_dir)}")
            except Exception as e:
                print(f"Errore nell'analisi della directory wasm3: {e}")
        
        # Scansione principale
        count = 0
        for file_path in scan_directory(start_path):
            count += 1
            yield file_path
        
        print(f"\n=== SCANSIONE COMPLETATA ===")
        print(f"Totale file trovati: {count}")


    def is_valid_source_file(self, file_path: Path) -> bool:
        """
        Verifica che il file sia un file sorgente C/C++ valido.
        """
        try:
            size = file_path.stat().st_size
            if size == 0 or size > 10 * 1024 * 1024:  # Skip empty files or files > 10MB
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                first_lines = ''.join(f.readline() for _ in range(5))
                cpp_indicators = ['#include', 'struct', 'class', 'void', 'int', '//']
                return any(indicator in first_lines for indicator in cpp_indicators)
                
        except (UnicodeDecodeError, IOError):
            return False
        
        return True

    def detect_circular_dependencies(self) -> List[List[str]]:
        try:
            cycles = list(nx.simple_cycles(self.dependency_graph))
            return cycles
        except nx.NetworkXNoCycle:
            return []

    def suggest_optimizations(self):
        suggestions = []
        
        cycles = self.detect_circular_dependencies()
        for cycle in cycles:
            suggestions.append(f"Dipendenza circolare trovata: {' -> '.join(cycle)}")
            
            types_in_cycle = set()
            for file in cycle:
                for type_name, type_info in self.type_declarations.items():
                    if type_info.file_path == file:
                        types_in_cycle.add(type_name)
            
            suggestions.append("\nSoluzioni possibili:")
            suggestions.append("1. Considera di creare un nuovo header file per questi tipi:")
            suggestions.extend([f"   - {t}" for t in types_in_cycle])
            suggestions.append("2. Usa forward declarations dove possibile")
            suggestions.append("3. Riorganizza le dichiarazioni per minimizzare le dipendenze\n")

        return "\n".join(suggestions)

    def analyze_project(self) -> str:
        """
        Analizza l'intero progetto cercando file in modo affidabile.
        """
        files_analyzed = 0
        files_skipped = 0
        errors = []

        print("Iniziando l'analisi del progetto...")
        
        try:
            for file_path in self.find_source_files(self.project_path):
                try:
                    print(f"Trovato: {file_path}")
                    
                    if not self.is_valid_source_file(file_path):
                        print(f"Saltato: {file_path} (non sembra un file sorgente C/C++ valido)")
                        files_skipped += 1
                        continue

                    print(f"Analizzando: {file_path}")
                    self.analyze_file(file_path)
                    files_analyzed += 1
                    
                except Exception as e:
                    error_msg = f"Errore nell'analisi di {file_path}: {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
                    files_skipped += 1

        except Exception as e:
            print(f"Errore critico durante l'analisi del progetto: {e}")
            return "Errore durante l'analisi del progetto"

        report = [
            "\nReport dell'analisi:",
            f"- File analizzati con successo: {files_analyzed}",
            f"- File saltati: {files_skipped}"
        ]
        
        if errors:
            report.append("\nErrori riscontrati:")
            report.extend(f"- {error}" for error in errors)

        report.append("\nAnalisi delle dipendenze:")
        report.append(self.suggest_optimizations())

        return '\n'.join(report)

def main():
    import sys
    if len(sys.argv) != 2:
        print("Uso: python script.py <percorso_progetto>")
        sys.exit(1)
        
    try:
        analyzer = HeaderDependencyAnalyzer(sys.argv[1])
        suggestions = analyzer.analyze_project()
        print("\nRisultati dell'analisi:")
        print(suggestions)
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")
        raise

if __name__ == "__main__":
    main()