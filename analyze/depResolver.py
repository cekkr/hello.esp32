import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Set, List, Optional
import re
from collections import defaultdict
import networkx as nx

@dataclass
class Type:
    """Rappresenta un tipo (struct/class/enum)"""
    name: str
    kind: str  # 'struct', 'class', 'enum'
    file_path: Path
    line_number: int
    dependencies: Set[str]  # altri tipi usati da questo tipo
    
@dataclass
class HeaderFile:
    """Rappresenta un file header"""
    path: Path
    includes: Set[str]
    types: Dict[str, Type]  # nome tipo -> definizione
    used_types: Set[str]  # tipi usati ma non definiti qui

class HeaderDependencyResolver:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.headers: Dict[Path, HeaderFile] = {}
        self.dependency_graph = nx.DiGraph()
        
    def analyze_project(self):
        """Analizza l'intero progetto"""
        # Trova tutti i file header
        header_files = self._find_headers()
        print(f"Trovati {len(header_files)} file header")
        
        # Analizza ogni file
        for header in header_files:
            self._analyze_header(header)
            
        # Costruisci il grafo delle dipendenze
        self._build_dependency_graph()
        
        # Trova e risolvi le dipendenze circolari
        self._resolve_circular_dependencies()
    
    def _find_headers(self) -> List[Path]:
        """Trova tutti i file header nel progetto"""
        headers = []
        for path in self.project_path.rglob("*.h"):
            if not any(p.name.startswith('.') for p in path.parents):
                headers.append(path)
        return headers
    
    def _analyze_header(self, path: Path):
        """Analizza un singolo file header"""
        print(f"Analisi {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Trova gli #include
            includes = set(re.findall(r'#include\s*[<"]([^>"]+)[>"]', content))
            
            # Analizza i tipi definiti
            types = self._find_types(content, path)
            
            # Trova i tipi usati
            used_types = self._find_used_types(content)
            
            self.headers[path] = HeaderFile(
                path=path,
                includes=includes,
                types=types,
                used_types=used_types
            )
            
        except Exception as e:
            print(f"Errore nell'analisi di {path}: {e}")
    
    def _find_types(self, content: str, file_path: Path) -> Dict[str, Type]:
        """Trova le definizioni di tipo nel file"""
        types = {}
        
        # Pattern per trovare definizioni di tipo
        type_pattern = r'''
            (struct|class|enum)\s+  # tipo di definizione
            (\w+)\s*               # nome del tipo
            {                      # inizio definizione
            ([^}]+)               # corpo della definizione
            }                     # fine definizione
        '''
        
        for match in re.finditer(type_pattern, content, re.VERBOSE | re.MULTILINE):
            kind, name, body = match.groups()
            line_number = content[:match.start()].count('\n') + 1
            
            # Trova le dipendenze nel corpo
            dependencies = set()
            for type_ref in re.finditer(r'\b(?:struct|class|enum)?\s+(\w+)\s*[\*&]?\s+\w+', body):
                dep_name = type_ref.group(1)
                if dep_name != name:  # evita auto-riferimenti
                    dependencies.add(dep_name)
            
            types[name] = Type(
                name=name,
                kind=kind,
                file_path=file_path,
                line_number=line_number,
                dependencies=dependencies
            )
        
        return types
    
    def _find_used_types(self, content: str) -> Set[str]:
        """Trova i tipi usati nel file"""
        used = set()
        for match in re.finditer(r'\b(?:struct|class|enum)?\s+(\w+)\s*[\*&]?\s+\w+', content):
            used.add(match.group(1))
        return used
    
    def _build_dependency_graph(self):
        """Costruisce il grafo delle dipendenze tra file"""
        for header in self.headers.values():
            # Aggiungi nodo per questo file
            self.dependency_graph.add_node(header.path)
            
            # Aggiungi dipendenze basate sugli #include
            for inc in header.includes:
                # Trova il path assoluto del file incluso
                inc_path = self._resolve_include_path(inc, header.path)
                if inc_path in self.headers:
                    self.dependency_graph.add_edge(header.path, inc_path)
            
            # Aggiungi dipendenze basate sui tipi usati
            for type_name in header.used_types:
                for other_header in self.headers.values():
                    if type_name in other_header.types:
                        self.dependency_graph.add_edge(header.path, other_header.path)
    
    def _resolve_include_path(self, include: str, from_file: Path) -> Optional[Path]:
        """Risolve il path assoluto di un file incluso"""
        if include.startswith('<'):
            # System header, ignora
            return None
            
        # Rimuovi virgolette
        include = include.strip('"')
        
        # Prova prima relativamente al file corrente
        resolved = from_file.parent / include
        if resolved.exists():
            return resolved
            
        # Poi prova relativamente alla root del progetto
        resolved = self.project_path / include
        if resolved.exists():
            return resolved
            
        return None
    
    def _resolve_circular_dependencies(self):
        """Trova e risolvi le dipendenze circolari"""
        # Trova i cicli
        cycles = list(nx.simple_cycles(self.dependency_graph))
        if not cycles:
            print("Nessuna dipendenza circolare trovata")
            return
            
        print(f"Trovati {len(cycles)} cicli di dipendenze")
        
        for cycle in cycles:
            print(f"\nRisoluzione ciclo: {' -> '.join(str(p) for p in cycle)}")
            
            # Trova il miglior punto dove spezzare il ciclo
            break_point = self._find_break_point(cycle)
            
            # Crea forward declarations
            self._create_forward_declarations(cycle, break_point)
            
            # Riorganizza gli #include
            self._reorder_includes(cycle, break_point)
    
    def _find_break_point(self, cycle: List[Path]) -> Path:
        """Trova il miglior punto dove spezzare il ciclo"""
        # Scegli il file con meno tipi definiti
        return min(cycle, key=lambda p: len(self.headers[p].types))
    
    def _create_forward_declarations(self, cycle: List[Path], break_point: Path):
        """Crea forward declarations per spezzare il ciclo"""
        header = self.headers[break_point]
        
        # Trova i tipi che devono essere forward-declared
        types_to_declare = set()
        for type_name, type_def in header.types.items():
            for other_path in cycle:
                if other_path != break_point and type_name in self.headers[other_path].used_types:
                    types_to_declare.add((type_name, type_def.kind))
        
        if not types_to_declare:
            return
            
        # Crea un nuovo header per le forward declarations
        fwd_path = break_point.parent / f"{break_point.stem}_fwd.h"
        with open(fwd_path, 'w', encoding='utf-8') as f:
            f.write("#pragma once\n\n")
            for type_name, kind in sorted(types_to_declare):
                f.write(f"{kind} {type_name};\n")
        
        print(f"Create forward declarations in {fwd_path}")
    
    def _reorder_includes(self, cycle: List[Path], break_point: Path):
        """Riorganizza gli #include per risolvere il ciclo"""
        for path in cycle:
            if path == break_point:
                continue
                
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Trova tutti gli #include
                includes = re.finditer(r'(#include\s*[<"]([^>"]+)[>"])', content)
                includes = list(includes)
                
                # Riorganizza gli #include
                new_includes = []
                other_includes = []
                
                for match in includes:
                    full_include, inc_path = match.groups()
                    if any(inc_path in str(p) for p in cycle):
                        new_includes.append(full_include)
                    else:
                        other_includes.append(full_include)
                
                # Metti gli #include del ciclo dopo gli altri
                all_includes = other_includes + new_includes
                
                # Sostituisci la sezione degli #include
                new_content = re.sub(
                    r'(#include\s*[<"][^>"]+[>"](\s*\n)?)+',
                    '\n'.join(all_includes) + '\n\n',
                    content,
                    count=1
                )
                
                # Salva il file modificato
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                print(f"Riordinati #include in {path}")
                
            except Exception as e:
                print(f"Errore nel riordino degli #include in {path}: {e}")

def main():
    import sys
    if len(sys.argv) != 2:
        print("Uso: python script.py <percorso_progetto>")
        return
        
    resolver = HeaderDependencyResolver(sys.argv[1])
    resolver.analyze_project()

if __name__ == "__main__":
    main()