import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple, NamedTuple, Optional
from dataclasses import dataclass
import sys
from enum import Enum, auto
import os

class TypeKind(Enum):
    STRUCT = auto()
    CLASS = auto()
    TYPEDEF = auto()
    ENUM = auto()
    DEFINE = auto()
    UNKNOWN = auto()

@dataclass
class TypeDefinition:
    name: str
    kind: TypeKind
    line: int
    content: str
    
@dataclass
class Include:
    path: Path
    line: int
    is_system: bool  # True per <>, False per ""

@dataclass
class HeaderFile:
    path: Path
    types: List[TypeDefinition]
    includes: List[Include]
    included_by: Set[Path]
    raw_content: Optional[str] = None
    
    def __hash__(self):
        return hash(self.path)
        
    def add_include(self, include: Include):
        self.includes.append(include)
        
    def add_type(self, type_def: TypeDefinition):
        self.types.append(type_def)
        
    def find_type(self, name: str) -> Optional[TypeDefinition]:
        return next((t for t in self.types if t.name == name), None)

class CompilationIssue(NamedTuple):
    file: Path
    line: int
    type: str
    message: str
    symbol: str = None

class HeaderAnalyzer:
    MAX_RECURSION_DEPTH = 100
    HEADER_EXTENSIONS = {'.h', '.hpp', '.hxx', '.h++'}
    
    def __init__(self, project_paths: List[str]):
        if isinstance(project_paths, str):
            project_paths = [project_paths]
            
        self.project_paths = [Path(p).resolve() for p in project_paths]
        print("Directory di progetto normalizzate:")
        for path in self.project_paths:
            print(f"  - {path}")
            
        self.files: Dict[Path, HeaderFile] = {}
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.includes_order = defaultdict(list)
        self.type_definitions = defaultdict(list)
        self.type_usages = defaultdict(list)
        self._initialize_files()
    
    def _get_include_path(self, included_path: str, current_file: Path) -> Optional[Path]:
        """Risolve il path completo di un file incluso."""
        try:
            # Prova prima il path relativo al file corrente
            relative_path = (current_file.parent / included_path).resolve()
            if self.is_project_file(relative_path):
                return relative_path
                
            # Poi prova nelle directory del progetto
            for project_path in self.project_paths:
                potential_path = (project_path / included_path).resolve()
                if self.is_project_file(potential_path):
                    return potential_path
            
            return None
            
        except Exception:
            return None

    def _parse_header_file(self, file_path: Path) -> Optional[HeaderFile]:
        """Analizza un file header e crea un oggetto HeaderFile."""
        if file_path in self.files:
            return self.files[file_path]
            
        try:
            if not self.is_project_file(file_path) or not file_path.is_file():
                return None
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                print(f"Errore di codifica in {file_path.name}")
                return None
            
            header = HeaderFile(
                path=file_path,
                types=[],
                includes=[],
                included_by=set(),
                raw_content=content
            )
            
            # Analizza le inclusioni
            include_pattern = re.compile(r'#include\s*[<"]([^>"]+)[>"]')
            for match in include_pattern.finditer(content):
                included_path = match.group(1)
                is_system = match.group(0).strip().endswith('>')
                line_num = content[:match.start()].count('\n') + 1
                
                resolved_path = self._get_include_path(included_path, file_path)
                if resolved_path:
                    include = Include(resolved_path, line_num, is_system)
                    header.add_include(include)
                    self.include_graph[file_path].add(resolved_path)
                    self.reverse_graph[resolved_path].add(file_path)
            
            self._parse_type_definitions(header, content)
            self.files[file_path] = header
            return header
            
        except Exception as e:
            print(f"Errore analizzando {file_path}: {e}")
            return None

    def is_header_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.HEADER_EXTENSIONS

    def is_project_file(self, file_path: Path) -> bool:
        try:
            if not file_path or not self.is_header_file(file_path):
                return False
                
            file_path = file_path.resolve()
            
            if not file_path.is_absolute():
                return False
            
            is_in_project = any(
                str(file_path).startswith(str(proj_path))
                for proj_path in self.project_paths
            )
            
            if not is_in_project:
                return False
            
            system_dirs = {'System', 'Library', 'usr', 'include', 'frameworks'}
            if any(part.lower() in system_dirs for part in file_path.parts):
                return False
            
            return True
            
        except Exception as e:
            print(f"Errore verificando il path {file_path}: {e}")
            return False

    def _initialize_files(self):
        found_files = set()
        
        for path in self.project_paths:
            if not path.is_dir():
                print(f"ATTENZIONE: {path} non è una directory valida")
                continue
            
            print(f"\nScansione directory: {path}")
            try:
                for file_path in path.rglob('*'):
                    if self.is_project_file(file_path):
                        found_files.add(file_path)
            except Exception as e:
                print(f"Errore durante la scansione di {path}: {e}")
        
        print(f"\nTrovati {len(found_files)} file header nel progetto:")
        for file_path in sorted(found_files):
            try:
                rel_path = file_path.relative_to(file_path.parent.parent)
                print(f"  - {rel_path}")
                self._parse_header_file(file_path)
            except Exception as e:
                print(f"Errore nel parsing di {file_path}: {e}")

    def _parse_type_definitions(self, header: HeaderFile, content: str):
        """Analizza il contenuto per trovare definizioni di tipi."""
        # Struct e Class
        for match in re.finditer(r'(struct|class)\s+(\w+)\s*\{', content):
            kind = TypeKind.STRUCT if match.group(1) == 'struct' else TypeKind.CLASS
            name = match.group(2)
            line = content[:match.start()].count('\n') + 1
            header.add_type(TypeDefinition(name, kind, line, match.group(0)))
            
        # Typedef
        for match in re.finditer(r'typedef\s+.*?\s+(\w+)\s*;', content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1

            header.add_type(TypeDefinition(name, TypeKind.TYPEDEF, line, match.group(0)))
            
        # Enum
        for match in re.finditer(r'enum\s+(\w+)\s*\{', content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            header.add_type(TypeDefinition(name, TypeKind.ENUM, line, match.group(0)))
            
        # Define
        for match in re.finditer(r'#define\s+(\w+)\s+', content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            header.add_type(TypeDefinition(name, TypeKind.DEFINE, line, match.group(0)))

    def parse_build_log(self, log_content: str) -> List[CompilationIssue]:
        """Analizza il log di compilazione per trovare errori."""
        issues = []
        include_stack = []
        
        include_pattern = re.compile(r'\.+\s(/[^:\n]+)')
        error_pattern = re.compile(r'([^:]+):(\d+)(?::\d+)?: (error|warning): (.+)')
        type_error_pattern = re.compile(r'unknown type name [\'"]([^\'\"]+)[\'"]|forward declaration of [\'"]struct ([^\'\"]+)[\'"]')
        
        for i, line in enumerate(log_content.splitlines()):
            include_match = include_pattern.match(line)
            if include_match:
                included_file = Path(include_match.group(1))
                if not self.is_project_file(included_file):
                    continue
                    
                dots_count = len(line) - len(line.lstrip('.'))
                while len(include_stack) > dots_count:
                    include_stack.pop()
                
                if include_stack:
                    parent = include_stack[-1]
                    if self.is_project_file(parent):
                        self.include_graph[parent].add(included_file)
                        self.reverse_graph[included_file].add(parent)
                        self.includes_order[parent].append((included_file, i))
                
                include_stack.append(included_file)
                continue
            
            error_match = error_pattern.match(line)
            if error_match and include_stack:
                file_path = Path(error_match.group(1))
                if not self.is_project_file(file_path):
                    continue
                    
                line_num = int(error_match.group(2))
                issue_type = error_match.group(3)
                message = error_match.group(4)
                
                type_match = type_error_pattern.search(message)
                if type_match:
                    type_name = type_match.group(1) or type_match.group(2)
                    issue = CompilationIssue(
                        file=file_path,
                        line=line_num,
                        type=issue_type,
                        message=message,
                        symbol=type_name
                    )
                    issues.append(issue)
                    self.type_usages[type_name].append((file_path, line_num))
        
        return issues

    def analyze_type_issue(self, issue: CompilationIssue):
        """Analizza un problema di tipo non trovato."""
        print(f"\n=== Analisi del tipo '{issue.symbol}' non trovato in {issue.file.name}:{issue.line} ===\n")
        
        # Mostra le inclusioni del file con l'errore
        if issue.file in self.files:
            current_file = self.files[issue.file]
            print(f"File con l'errore ({issue.file.name}) include:")
            for inc in current_file.includes:
                print(f"  - {inc.path.name} (linea {inc.line})")
        else:
            print(f"ATTENZIONE: File con l'errore {issue.file.name} non trovato nel progetto")
        
        # Trova i file che definiscono il tipo
        defining_files = []
        for header in self.files.values():
            if any(t.name == issue.symbol for t in header.types):
                defining_files.append(header)
        
        if defining_files:
            print(f"\nIl tipo '{issue.symbol}' è definito in:")
            for header in defining_files:
                type_def = header.find_type(issue.symbol)
                print(f"  {header.path.name}:{type_def.line} -> {type_def.content}")
                
                # Mostra chi include questo file di definizione
                if header.path in self.reverse_graph:
                    included_by = self.reverse_graph[header.path]
                    if included_by:
                        print(f"  {header.path.name} è incluso da:")
                        for including_file in included_by:
                            if including_file in self.files:
                                inc_file = self.files[including_file]
                                for inc in inc_file.includes:
                                    if inc.path == header.path:
                                        print(f"    - {including_file.name} (linea {inc.line})")
                    else:
                        print(f"  {header.path.name} non è incluso da nessun file nel progetto")
                
                # Cerca cicli di inclusione che potrebbero interferire
                cycles = self._find_cycles_between_files(issue.file, header.path)
                if cycles:
                    print(f"\nATTENZIONE: Trovati cicli di inclusione tra {issue.file.name} e {header.path.name}:")
                    for cycle in cycles:
                        print("  " + " -> ".join(p.name for p in cycle))
            
            print("\nAnalisi dei percorsi di inclusione:")
            for header in defining_files:
                paths = self.find_type_definition_paths(issue.file, issue.symbol)
                if paths:
                    print(f"\nPercorsi da {issue.file.name} a {header.path.name}:")
                    for path in sorted(paths, key=len):
                        print("  " + " -> ".join(p.name for p in path))
                else:
                    print(f"\nNessun percorso di inclusione trovato verso {header.path.name}")
        else:
            print(f"\nIl tipo '{issue.symbol}' non è definito in nessun header del progetto")

    def _find_cycles_between_files(self, file1: Path, file2: Path, max_depth=10) -> List[List[Path]]:
        """Trova tutti i cicli di inclusione tra due file."""
        cycles = []
        visited = set()
        
        def dfs(current: Path, target: Path, path: List[Path], depth: int = 0):
            if depth > max_depth:
                return
                
            if current == target and len(path) > 1:
                cycles.append(path + [current])
                return
                
            if current in path:
                return
                
            for next_file in self.include_graph[current]:
                if next_file not in visited:
                    visited.add(next_file)
                    dfs(next_file, target, path + [current], depth + 1)
                    visited.remove(next_file)
        
    def find_type_definition_paths(self, from_file: Path, type_name: str, depth=0) -> List[List[Path]]:
        """Trova tutti i percorsi possibili alla definizione di un tipo."""
        if depth > self.MAX_RECURSION_DEPTH:
            return []
            
        def dfs(current: Path, visited: Set[Path], path: List[Path], current_depth: int) -> List[List[Path]]:
            if current_depth > self.MAX_RECURSION_DEPTH:
                return []
                
            if current in visited:
                return []
                
            visited.add(current)
            paths = []
            
            if current in self.files:
                header = self.files[current]
                if any(t.name == type_name for t in header.types):
                    return [path + [current]]
            
            for next_file in self.include_graph[current]:
                if next_file not in visited:
                    for new_path in dfs(next_file, visited.copy(), path + [current], current_depth + 1):
                        paths.append(new_path)
            
            return paths
            
        return dfs(from_file, set(), [], 0)

def main():
    if len(sys.argv) < 2:
        print("Uso: python cHeaderAnalyzer.py <log_file> [project_path]")
        sys.exit(1)

    log_path = sys.argv[1]
    project_path = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(log_path)

    try:
        with open(log_path, 'r') as f:
            log_content = f.read()
        
        analyzer = HeaderAnalyzer([project_path])
        issues = analyzer.parse_build_log(log_content)
        
        type_issues = [issue for issue in issues if issue.symbol]
        if not type_issues:
            print("Nessun problema di tipo non trovato nel log.")
            return
            
        for issue in type_issues:
            analyzer.analyze_type_issue(issue)
            input("\nPremi Enter per analizzare il prossimo problema...")
            
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")
        raise

if __name__ == "__main__":
    main()

# python3 cHeaderAnalyzer.py ../hello-idf/build_output.txt