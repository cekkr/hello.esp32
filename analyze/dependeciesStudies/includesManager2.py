from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional, Callable
from pathlib import Path
from collections import defaultdict
import re

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
    
    def add_definition(self, symbol: SymbolDefinition):
        self.definitions[symbol.name].append(symbol)
        
    def add_usage(self, usage: SymbolUsage):
        self.usages[usage.name].append(usage)
        # Update symbol dependencies
        for req in usage.required_symbols:
            self.dependencies[usage.name].add(req)
    
    def get_symbol_providers(self, symbol_name: str) -> List[Path]:
        """Get all files that provide a given symbol"""
        return [def_.file for def_ in self.definitions.get(symbol_name, [])]
    
    def get_symbol_dependencies(self, symbol_name: str) -> Set[str]:
        """Get all symbols that a given symbol depends on"""
        direct_deps = self.dependencies.get(symbol_name, set())
        all_deps = set(direct_deps)
        
        # Recursively get transitive dependencies
        for dep in direct_deps:
            all_deps.update(self.get_symbol_dependencies(dep))
            
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
        
    def analyze(self):
        """Main analysis workflow"""
        self._build_symbol_table()
        self._analyze_dependencies()
        self._resolve_include_order()
        
    def _build_symbol_table(self):
        """Build global symbol table from source files"""
        for path, source in self.source_files.items():
            # Process definitions
            for def_ in source.definitions:
                symbol_def = SymbolDefinition(
                    name=def_.name,
                    kind=def_.kind,
                    file=path,
                    line=def_.line,
                    scope=def_.context,
                    dependencies=self._extract_dependencies(def_.context)
                )
                self.symbol_table.add_definition(symbol_def)
                
            # Process usages
            for usage in source.usages:
                symbol_usage = SymbolUsage(
                    name=usage.name,
                    file=path,
                    line=usage.line,
                    context=usage.context,
                    required_symbols=self._extract_dependencies(usage.context)
                )
                self.symbol_table.add_usage(symbol_usage)
                
    def _analyze_dependencies(self):
        """Analyze header dependencies and build dependency graph"""
        for path, source in self.source_files.items():
            if not source.is_header:
                continue
                
            deps = HeaderDependencies(path)
            
            # Add symbols provided by this header
            for def_ in source.definitions:
                deps.add_provided_symbol(def_.name)
                
            # Add symbols required by this header
            for usage in source.usages:
                deps.add_required_symbol(usage.name)
                
            # Add direct includes
            for include in source.includes:
                deps.add_include(include)
                
            self.header_deps[path] = deps
            
        # Build transitive includes and dependents
        self._build_transitive_relations()
        
    def _build_transitive_relations(self):
        """Build transitive include relationships"""
        changed = True
        while changed:
            changed = False
            for deps in self.header_deps.values():
                old_size = len(deps.transitive_includes)
                
                # Add includes from direct includes
                for direct in deps.direct_includes:
                    if direct in self.header_deps:
                        deps.transitive_includes.update(
                            self.header_deps[direct].transitive_includes
                        )
                        
                if len(deps.transitive_includes) > old_size:
                    changed = True
                    
        # Build dependent relationships
        for path, deps in self.header_deps.items():
            for inc in deps.direct_includes:
                if inc in self.header_deps:
                    self.header_deps[inc].dependents.add(path)
                    
    def _resolve_include_order(self):
        """Determine optimal include order for each header"""
        # Process headers in dependency order
        processed = set()
        
        def process_header(path: Path) -> List[Path]:
            if path in processed:
                return self.include_order.get(path, [])
                
            deps = self.header_deps[path]
            order = []
            
            # First process all dependencies
            for inc in deps.direct_includes:
                if inc in self.header_deps and inc not in processed:
                    order.extend(process_header(inc))
                    
            # Add this header's includes in optimal order
            required_symbols = deps.required_symbols
            remaining_includes = set(deps.direct_includes)
            
            while required_symbols and remaining_includes:
                best_include = self._find_best_include(
                    required_symbols, remaining_includes
                )
                if not best_include:
                    break
                    
                order.append(best_include)
                remaining_includes.remove(best_include)
                
                # Update remaining required symbols
                if best_include in self.header_deps:
                    provided = self.header_deps[best_include].provided_symbols
                    required_symbols -= provided
                    
            # Add any remaining includes
            order.extend(remaining_includes)
            
            processed.add(path)
            self.include_order[path] = order
            return order
            
        # Process all headers
        for path in self.header_deps:
            if path not in processed:
                process_header(path)
                
    def _find_best_include(
        self, required_symbols: Set[str], candidates: Set[Path]
    ) -> Optional[Path]:
        """Find the include that provides the most required symbols"""
        best_include = None
        max_provided = 0
        
        for inc in candidates:
            if inc not in self.header_deps:
                continue
                
            provided = len(
                required_symbols & self.header_deps[inc].provided_symbols
            )
            if provided > max_provided:
                max_provided = provided
                best_include = inc
                
        return best_include
        
    def _extract_dependencies(self, context: str) -> Set[str]:
        """Extract symbol dependencies from context"""
        deps = set()
        words = re.findall(r'\b\w+\b', context)
        for word in words:
            if word in self.symbol_table.definitions:
                deps.add(word)
        return deps
        
    def get_include_order(self, file_path: Path) -> List[Path]:
        """Get the optimal include order for a file"""
        return self.include_order.get(file_path, [])
        
    def verify_includes(self) -> dict:
        """Verify include relationships and identify issues"""
        issues = {
            'missing_symbols': defaultdict(set),
            'circular_deps': [],
            'unnecessary_includes': defaultdict(set)
        }
        
        # Check for missing symbols
        for path, deps in self.header_deps.items():
            available_symbols = set()
            for inc in self.get_include_order(path):
                if inc in self.header_deps:
                    available_symbols.update(
                        self.header_deps[inc].provided_symbols
                    )
            
            missing = deps.required_symbols - available_symbols
            if missing:
                issues['missing_symbols'][str(path)] = missing
                
        # Find circular dependencies
        issues['circular_deps'] = self._find_circular_deps()
        
        # Find unnecessary includes
        for path, deps in self.header_deps.items():
            required_symbols = deps.required_symbols
            for inc in deps.direct_includes:
                if inc not in self.header_deps:
                    continue
                    
                if not (required_symbols & 
                       self.header_deps[inc].provided_symbols):
                    issues['unnecessary_includes'][str(path)].add(str(inc))
                    
        return issues
        
    def _find_circular_deps(self) -> List[List[str]]:
        """Find circular dependencies in the include graph"""
        cycles = []
        visited = set()
        path_stack = []
        
        def dfs(current: Path):
            if current in path_stack:
                start = path_stack.index(current)
                cycle = [str(p) for p in path_stack[start:]]
                cycles.append(cycle)
                return
                
            if current in visited:
                return
                
            visited.add(current)
            path_stack.append(current)
            
            if current in self.header_deps:
                for inc in self.header_deps[current].direct_includes:
                    dfs(inc)
                    
            path_stack.pop()
            
        # Start DFS from each header
        for header in self.header_deps:
            if header not in visited:
                dfs(header)
                
        return cycles