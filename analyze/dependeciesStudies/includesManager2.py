from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional, Callable
from pathlib import Path
from collections import defaultdict
import re
import contextlib
from readCLib import *

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

    def get_symbol_dependencies(self, symbol_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """
        Get all symbols that a given symbol depends on, avoiding circular dependencies.

        Args:
            symbol_name: Name of the symbol to analyze
            visited: Set of already visited symbols in the current recursion path

        Returns:
            Set of all dependent symbols
        """
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

    def get_source_analysis(self) -> Dict[str, dict]:
        """
        Get comprehensive analysis for all source files.
        Returns a dictionary with file paths as keys and detailed analysis as values.
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
                    'provided': [],  # Will contain detailed symbol info
                    'required': [],  # Will contain detailed symbol info
                },
                'includes': {
                    'optimal_order': [str(p) for p in self.get_include_order(path)],
                    'current': [str(p) for p in source.includes],
                    'direct': [],
                    'transitive': [],
                    'unnecessary': []
                },
                'dependencies': {
                    'dependent_files': [],  # Files that depend on this one
                    'dependency_chain': self._get_dependency_chain(path),
                },
                'analysis': {
                    'has_circular_deps': False,
                    'missing_symbols': [],
                    'symbol_overlap': [],  # Symbols provided by multiple includes
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
            
            # Add analysis information
            self._add_analysis_info(source_info, path)
            
            sources[str_path] = source_info
            
        return sources
    
    def _get_symbol_info(self, symbol_name: str, file_path: Path) -> dict:
        """Get detailed information about a symbol"""
        symbol_info = {
            'name': symbol_name,
            'type': 'unknown',
            'definitions': [],
            'usages': [],
            'dependencies': list(self.symbol_table.get_symbol_dependencies(symbol_name))
        }
        
        # Add definition information
        for def_ in self.symbol_table.definitions.get(symbol_name, []):
            symbol_info['type'] = def_.kind
            def_info = {
                'file': str(def_.file),
                'line': def_.line,
                'scope': def_.scope,
                'is_exported': def_.is_exported
            }
            symbol_info['definitions'].append(def_info)
        
        # Add usage information
        for usage in self.symbol_table.usages.get(symbol_name, []):
            if usage.file == file_path:
                usage_info = {
                    'line': usage.line,
                    'context': usage.context,
                    'required_symbols': list(usage.required_symbols)
                }
                symbol_info['usages'].append(usage_info)
        
        return symbol_info
    
    def _get_dependency_chain(self, path: Path) -> List[List[str]]:
        """Get all possible dependency chains for a file"""
        chains = []
        visited = set()
        
        def build_chain(current: Path, current_chain: List[Path]):
            if current in visited:
                return
            
            visited.add(current)
            current_chain.append(current)
            
            if current in self.header_deps:
                deps = self.header_deps[current]
                if not deps.direct_includes:
                    chains.append([str(p) for p in current_chain])
                else:
                    for inc in deps.direct_includes:
                        build_chain(inc, current_chain[:])
            
            visited.remove(current)
        
        build_chain(path, [])
        return chains
    
    def _add_analysis_info(self, source_info: dict, path: Path):
        """Add analysis information to source info"""
        # Check for circular dependencies
        cycles = self._find_circular_deps()
        str_path = str(path)
        source_info['analysis']['has_circular_deps'] = any(
            str_path in cycle for cycle in cycles
        )
        
        # Find missing symbols
        if path in self.header_deps:
            deps = self.header_deps[path]
            available_symbols = set()
            
            for inc in self.get_include_order(path):
                if inc in self.header_deps:
                    available_symbols.update(
                        self.header_deps[inc].provided_symbols
                    )
            
            missing = deps.required_symbols - available_symbols
            source_info['analysis']['missing_symbols'] = list(missing)
        
        # Find symbol overlaps
        symbol_providers = defaultdict(list)
        if path in self.header_deps:
            for inc in self.header_deps[path].direct_includes:
                if inc in self.header_deps:
                    for symbol in self.header_deps[inc].provided_symbols:
                        symbol_providers[symbol].append(str(inc))
            
            overlaps = [
                {
                    'symbol': symbol,
                    'providers': providers
                }
                for symbol, providers in symbol_providers.items()
                if len(providers) > 1
            ]
            source_info['analysis']['symbol_overlap'] = overlaps
        
        # Generate include suggestions
        suggestions = self._generate_include_suggestions(path)
        source_info['analysis']['include_suggestions'] = suggestions
    
    def _generate_include_suggestions(self, path: Path) -> List[dict]:
        """Generate suggestions for improving includes"""
        suggestions = []
        
        if path in self.header_deps:
            deps = self.header_deps[path]
            current_order = [str(p) for p in deps.direct_includes]
            optimal_order = [str(p) for p in self.get_include_order(path)]
            
            if current_order != optimal_order:
                suggestions.append({
                    'type': 'reorder',
                    'message': 'Consider reordering includes for better symbol resolution',
                    'current_order': current_order,
                    'suggested_order': optimal_order
                })
            
            # Check for unnecessary includes
            unnecessary = self._find_unnecessary_includes(path)
            if unnecessary:
                suggestions.append({
                    'type': 'remove',
                    'message': 'These includes might be unnecessary',
                    'includes': list(unnecessary)
                })
        
        return suggestions
    
    def _find_unnecessary_includes(self, path: Path) -> Set[str]:
        """Find includes that might be unnecessary"""
        unnecessary = set()
        
        if path in self.header_deps:
            deps = self.header_deps[path]
            required_symbols = deps.required_symbols
            
            for inc in deps.direct_includes:
                if inc not in self.header_deps:
                    continue
                    
                inc_symbols = self.header_deps[inc].provided_symbols
                if not (required_symbols & inc_symbols):
                    # Check if any transitive dependency needs this include
                    needed_by_transitive = False
                    for trans in deps.transitive_includes:
                        if inc in self.header_deps[trans].direct_includes:
                            needed_by_transitive = True
                            break
                    
                    if not needed_by_transitive:
                        unnecessary.add(str(inc))
        
        return unnecessary