from dataclasses import dataclass
from typing import Dict, Set, List, Optional, Tuple
from collections import defaultdict
import re
from pathlib import Path
import os

@dataclass
class TypeInfo:
    name: str
    defined_in: str
    used_in: Set[str]
    forward_declared_in: Set[str]
    dependencies: Set[str]
    definition_line: int

@dataclass
class FileInfo:
    path: str
    types_defined: Set[str]
    types_used: Set[str]
    includes: Set[str]
    forward_declarations: Set[str]

class HeaderDependencyAnalyzer:
    def __init__(self):
        self.files: Dict[str, FileInfo] = {}
        self.types: Dict[str, TypeInfo] = {}
        self.include_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_include_graph: Dict[str, Set[str]] = defaultdict(set)
        self.excluded_dirs = {'build', 'builds', '.git', '.svn', '__pycache__'}
    
    def print_directory_structure(self, startpath: str, level: int = 0):
        """Stampa la struttura completa della directory in formato ad albero"""
        print(f'{"  " * level}+ {os.path.basename(startpath)}/')
        
        try:
            items = sorted(os.listdir(startpath))
            for item in items:
                if item in self.excluded_dirs:
                    print(f'{"  " * (level + 1)}+ {item}/ [excluded]')
                    continue
                    
                path = os.path.join(startpath, item)
                if os.path.isdir(path):
                    self.print_directory_structure(path, level + 1)
                elif path.endswith(('.h', '.hpp', '.hxx', '.h++')):
                    print(f'{"  " * (level + 1)}- {item}')
        except PermissionError:
            print(f'{"  " * (level + 1)}! Permission denied')
        except Exception as e:
            print(f'{"  " * (level + 1)}! Error: {str(e)}')

    def find_header_files(self, start_path: str, verbose: bool = True) -> List[Path]:
        """Trova ricorsivamente tutti i file header in una directory"""
        abs_start_path = os.path.abspath(start_path)
        if verbose:
            print(f"\nCercando header files in: {abs_start_path}")
            print("\nStruttura directory:")
            self.print_directory_structure(abs_start_path)
            print("\nLista dei file trovati:")
        
        header_files = []
        
        for root, dirs, files in os.walk(abs_start_path):
            # Modifica dirs in-place per escludere le directory non desiderate
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            
            if verbose:
                print(f"\nEsplorando directory: {root}")
            
            for file in files:
                if file.endswith(('.h', '.hpp', '.hxx', '.h++')):
                    full_path = Path(os.path.join(root, file))
                    header_files.append(full_path)
                    if verbose:
                        print(f"Trovato header: {full_path}")
        
        return header_files
    
    def analyze_file(self, filepath: str) -> None:
        """Analizza un singolo file header"""
        with open(filepath, 'r') as f:
            content = f.read()
            
        file_info = FileInfo(
            path=filepath,
            types_defined=set(),
            types_used=set(),
            includes=set(),
            forward_declarations=set()
        )
        
        # Trova gli include
        for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
            included_file = match.group(1)
            file_info.includes.add(included_file)
            self.include_graph[filepath].add(included_file)
            self.reverse_include_graph[included_file].add(filepath)
        
        # Trova le definizioni di tipo (struct/class/enum)
        for match in re.finditer(r'(struct|class|enum)\s+(\w+)\s*{([^}]+)}', content):
            type_kind, type_name, definition = match.groups()
            file_info.types_defined.add(type_name)
            
            # Analizza le dipendenze nella definizione
            dependencies = set()
            for dep_match in re.finditer(r'(struct|class|enum)\s+(\w+)', definition):
                dep_type = dep_match.group(2)
                if dep_type != type_name:  # Ignora auto-riferimenti
                    dependencies.add(dep_type)
                    file_info.types_used.add(dep_type)
            
            self.types[type_name] = TypeInfo(
                name=type_name,
                defined_in=filepath,
                used_in=set(),
                forward_declared_in=set(),
                dependencies=dependencies,
                definition_line=content[:match.start()].count('\n') + 1
            )
        
        # Trova le forward declarations
        for match in re.finditer(r'(struct|class|enum)\s+(\w+)\s*;', content):
            type_name = match.group(2)
            file_info.forward_declarations.add(type_name)
            if type_name in self.types:
                self.types[type_name].forward_declared_in.add(filepath)
        
        self.files[filepath] = file_info
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Trova tutti i cicli di dipendenze usando DFS"""
        def dfs(node: str, visited: Set[str], path: List[str]) -> List[List[str]]:
            cycles = []
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:])
                return cycles
            
            if node in visited:
                return cycles
            
            visited.add(node)
            path.append(node)
            
            for neighbor in self.include_graph[node]:
                cycles.extend(dfs(neighbor, visited.copy(), path.copy()))
            
            return cycles
        
        all_cycles = []
        for file in self.files:
            cycles = dfs(file, set(), [])
            all_cycles.extend(cycles)
        
        return [cycle for cycle in all_cycles if len(cycle) > 1]
    
    def optimize_includes(self) -> Dict[str, Dict[str, str]]:
        """
        Calcola l'ordine ottimale delle inclusioni e suggerisce modifiche
        Returns: Dict[file_path, Dict[suggestion_type, suggestion]]
        """
        suggestions = defaultdict(dict)
        cycles = self.find_circular_dependencies()
        
        # Analizza ogni ciclo di dipendenze
        for cycle in cycles:
            # Trova i tipi coinvolti nel ciclo
            cycle_types = set()
            for file in cycle:
                file_info = self.files[file]
                cycle_types.update(file_info.types_defined)
                cycle_types.update(file_info.types_used)
            
            # Per ogni file nel ciclo
            for i, file in enumerate(cycle):
                file_info = self.files[file]
                next_file = cycle[(i + 1) % len(cycle)]
                next_file_info = self.files[next_file]
                
                # Trova i tipi che causano la dipendenza circolare
                problematic_types = file_info.types_used.intersection(
                    next_file_info.types_defined
                )
                
                if problematic_types:
                    # Decidi se fare forward declaration o creare nuovo header
                    if len(problematic_types) <= 2:
                        # Suggerisci forward declarations
                        forward_decls = "\n".join(
                            f"struct {t};" for t in problematic_types
                        )
                        suggestions[file]["forward_declarations"] = (
                            f"// Add these forward declarations at the top:\n{forward_decls}"
                        )
                    else:
                        # Suggerisci nuovo file di dichiarazioni
                        new_header = f"{Path(file).stem}_fwd.h"
                        declarations = "\n".join(
                            f"struct {t};" for t in problematic_types
                        )
                        suggestions[file]["new_header"] = {
                            "name": new_header,
                            "content": f"#pragma once\n\n{declarations}",
                            "message": f"Create new header {new_header} with forward declarations"
                        }
                        
                    # Suggerisci riordinamento degli include
                    current_includes = list(file_info.includes)
                    optimized_includes = self._optimize_include_order(
                        file, current_includes, problematic_types
                    )
                    if current_includes != optimized_includes:
                        suggestions[file]["reorder_includes"] = {
                            "message": "Reorder includes as follows:",
                            "order": optimized_includes
                        }
        
        return suggestions
    
    def _optimize_include_order(
        self, file: str, current_includes: List[str], 
        problematic_types: Set[str]
    ) -> List[str]:
        """Ottimizza l'ordine degli include per un file"""
        # Separa gli include in tre gruppi
        system_includes = []
        dependent_includes = []
        other_includes = []
        
        for inc in current_includes:
            if inc.startswith('<'):
                system_includes.append(inc)
            elif any(t in self.files.get(inc, FileInfo("", set(), set(), set(), set())).types_defined 
                    for t in problematic_types):
                dependent_includes.append(inc)
            else:
                other_includes.append(inc)
        
        # Riordina mettendo prima gli include non dipendenti
        return (
            system_includes +
            other_includes +
            dependent_includes
        )
    
    def print_analysis(self):
        """Stampa l'analisi completa e i suggerimenti"""
        print("\nAnalisi delle dipendenze circolari:")
        for cycle in self.find_circular_dependencies():
            print(f"\nCiclo trovato: {' -> '.join(cycle)}")
            
        print("\nSuggerimenti per ottimizzazione:")
        suggestions = self.optimize_includes()
        for file, file_suggestions in suggestions.items():
            print(f"\nPer il file {file}:")
            
            if "forward_declarations" in file_suggestions:
                print("\nAggiungere forward declarations:")
                print(file_suggestions["forward_declarations"])
            
            if "new_header" in file_suggestions:
                new_header = file_suggestions["new_header"]
                print(f"\nCreare nuovo file {new_header['name']}:")
                print(new_header["content"])
            
            if "reorder_includes" in file_suggestions:
                reorder = file_suggestions["reorder_includes"]
                print("\nRiordinare gli include:")
                for inc in reorder["order"]:
                    print(f"#include {inc}")

def main():
    analyzer = HeaderDependencyAnalyzer()
    
    base_path = '../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi'
    abs_base_path = os.path.abspath(base_path)
    
    print(f"\nPercorso di base: {base_path}")
    print(f"Percorso assoluto: {abs_base_path}")
    
    # Verifica l'esistenza della directory main
    if False:
        main_path = os.path.join(abs_base_path, 'wasm3')
        if os.path.exists(main_path):
            print(f"\nLa directory main esiste in: {main_path}")
            print("Contenuto della directory main:")
            try:
                for item in os.listdir(main_path):
                    print(f" - {item}")
            except Exception as e:
                print(f"Errore nel leggere la directory main: {e}")
        else:
            print(f"\nLa directory main NON esiste in: {main_path}")
            print("Directory genitore contiene:")
            try:
                for item in os.listdir(abs_base_path):
                    print(f" - {item}")
            except Exception as e:
                print(f"Errore nel leggere la directory: {e}")
        
    # Trova e analizza i file header
    header_files = analyzer.find_header_files(abs_base_path, verbose=True)
    
    print(f"\nTrovati {len(header_files)} file header")
    
    for file in header_files:
        try:
            analyzer.analyze_file(str(file))
        except Exception as e:
            print(f"Errore nell'analisi di {file}: {e}")
    
    analyzer.print_analysis()



if __name__ == "__main__":
    main()