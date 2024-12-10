from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional, Callable
from collections import defaultdict
import json
import re
from readCLib import *

@dataclass
class Symbol:
    name: str
    kind: str
    context: str
    defined_in: Optional[Path] = None
    used_in: Set[Path] = field(default_factory=set)
    required_symbols: Set[str] = field(default_factory=set)

@dataclass
class FileIncludes:
    path: Path
    direct_includes: Set[Path]
    indirect_includes: Set[Path]
    required_symbols: Set[str]
    provided_symbols: Set[str]
    include_order: List[Path]
    missing_symbols: Set[str]
    circular_dependencies: List[List[Path]]
    
    @property
    def all_includes(self) -> Set[Path]:
        return self.direct_includes | self.indirect_includes

@dataclass
class IncludeChain:
    header_path: Path
    symbols_available: Set[str]
    symbols_required: Set[str]
    dependencies: List[Path]
    is_valid: bool
    missing_symbols: Set[str] = field(default_factory=set)
    
    def validate(self, symbol_registry: Dict[str, Symbol]) -> bool:
        """Validates if all required symbols are available through the include chain"""
        available = set()
        for dep in self.dependencies:
            if dep in symbol_registry:
                available.update(symbol_registry[dep].provided_symbols)
        
        self.missing_symbols = self.symbols_required - available
        self.is_valid = len(self.missing_symbols) == 0
        return self.is_valid

@dataclass
class ProjectAnalysis:
    source_files: Dict[Path, FileIncludes]
    symbol_registry: Dict[str, Symbol]
    include_chains: Dict[Path, IncludeChain]
    validation_errors: Dict[Path, List[str]]
    
    def get_file_includes(self, path: Path) -> Optional[FileIncludes]:
        return self.source_files.get(path)
    
    def get_symbol_info(self, symbol_name: str) -> Optional[Symbol]:
        return self.symbol_registry.get(symbol_name)
    
    def get_include_chain(self, path: Path) -> Optional[IncludeChain]:
        return self.include_chains.get(path)

    def get_file_includes_by_suffix(self, suffix: str) -> Optional[FileIncludes]:
        """
        Trova il primo FileIncludes la cui path termina con il suffisso specificato.
        
        Args:
            source_files: Dizionario che mappa Path a FileIncludes
            suffix: Stringa da cercare come suffisso del path
            
        Returns:
            FileIncludes se trovato, None altrimenti
        """
        for path, file_includes in self.source_files.items():
            if str(path).endswith(suffix):
                return file_includes
        
        return None

@dataclass
class EnhancedIncludeResolver:
    source_path: Path
    analyzer: Optional[SourceAnalyzer] = None
    project_analysis: Optional[ProjectAnalysis] = None
    
    def __post_init__(self):
        self.analyzer = SourceAnalyzer(str(self.source_path))
        self.analyze_project()
    
    def analyze_project(self):
        """Performs complete project analysis and builds include chains for all files"""
        self.analyzer.analyze()
        
        source_files = {}
        symbol_registry = {}
        include_chains = {}
        validation_errors = defaultdict(list)
        
        # First pass: collect all symbols and their locations
        for path, source_file in self.analyzer.files.items():
            # Build symbol registry
            for symbol in source_file.definitions:
                if symbol.name not in symbol_registry:
                    symbol_registry[symbol.name] = Symbol(
                        name=symbol.name,
                        kind=symbol.kind,
                        context=symbol.context,
                        defined_in=path,
                        used_in=set(),
                        required_symbols=self._extract_dependencies(symbol.context)
                    )
            
            # Track symbol usage
            for usage in source_file.usages:
                if usage.name in symbol_registry:
                    symbol_registry[usage.name].used_in.add(path)
        
        # Second pass: build include chains and validate them
        for path, source_file in self.analyzer.files.items():
            direct_includes = set(source_file.includes)
            indirect_includes = self._calculate_indirect_includes(direct_includes)
            required_symbols = {s.name for s in source_file.usages}
            provided_symbols = {s.name for s in source_file.definitions}
            
            # Calculate optimal include order
            include_order = self._determine_include_order(
                path,
                required_symbols,
                direct_includes,
                symbol_registry
            )
            
            # Validate the include chain
            missing_symbols = self._validate_includes(
                path,
                include_order,
                required_symbols,
                symbol_registry
            )
            
            # Check for circular dependencies
            circular_deps = self._find_circular_dependencies(path, include_order)
            
            # Store file analysis
            source_files[path] = FileIncludes(
                path=path,
                direct_includes=direct_includes,
                indirect_includes=indirect_includes,
                required_symbols=required_symbols,
                provided_symbols=provided_symbols,
                include_order=include_order,
                missing_symbols=missing_symbols,
                circular_dependencies=circular_deps
            )
            
            # Create include chain
            include_chains[path] = IncludeChain(
                header_path=path,
                symbols_available=self._get_available_symbols(include_order, symbol_registry),
                symbols_required=required_symbols,
                dependencies=include_order,
                is_valid=len(missing_symbols) == 0
            )
            
            # Store any validation errors
            if missing_symbols:
                validation_errors[path].append(
                    f"Missing symbols: {', '.join(missing_symbols)}"
                )
            if circular_deps:
                validation_errors[path].append(
                    f"Circular dependencies detected: {circular_deps}"
                )
        
        self.project_analysis = ProjectAnalysis(
            source_files=source_files,
            symbol_registry=symbol_registry,
            include_chains=include_chains,
            validation_errors=dict(validation_errors)
        )
    
    def _extract_dependencies(self, context: str) -> Set[str]:
        """Extracts symbol dependencies from context"""
        dependencies = set()
        # Add more sophisticated dependency extraction if needed
        words = re.findall(r'\b\w+\b', context)
        return set(words)
    
    def _calculate_indirect_includes(self, direct_includes: Set[Path]) -> Set[Path]:
        """Calculates all indirect includes from direct includes"""
        indirect = set()
        for inc in direct_includes:
            if inc in self.analyzer.files:
                indirect.update(self.analyzer.files[inc].includes)
        return indirect
    
    def _determine_include_order(
        self,
        file_path: Path,
        required_symbols: Set[str],
        available_headers: Set[Path],
        symbol_registry: Dict[str, Symbol]
    ) -> List[Path]:
        """Determines optimal include order for a file"""
        def score_header(header: Path) -> int:
            """Scores a header based on how many required symbols it provides"""
            if header not in self.analyzer.files:
                return 0
            provides = {s.name for s in self.analyzer.files[header].definitions}
            return len(provides & required_symbols)
        
        # Sort headers by score
        scored_headers = [(h, score_header(h)) for h in available_headers]
        scored_headers.sort(key=lambda x: x[1], reverse=True)
        
        return [h for h, _ in scored_headers if h != file_path]
    
    def _validate_includes(
        self,
        file_path: Path,
        include_order: List[Path],
        required_symbols: Set[str],
        symbol_registry: Dict[str, Symbol]
    ) -> Set[str]:
        """Validates that all required symbols are available through includes"""
        available_symbols = self._get_available_symbols(include_order, symbol_registry)
        return required_symbols - available_symbols
    
    def _get_available_symbols(
        self,
        include_order: List[Path],
        symbol_registry: Dict[str, Symbol]
    ) -> Set[str]:
        """Gets all symbols available through a given include order"""
        available = set()
        for header in include_order:
            if header in self.analyzer.files:
                for symbol in self.analyzer.files[header].definitions:
                    available.add(symbol.name)
        return available
    
    def _find_circular_dependencies(
        self,
        file_path: Path,
        include_order: List[Path]
    ) -> List[List[Path]]:
        """Finds any circular dependencies in the include chain"""
        def find_cycles(graph: Dict[Path, Set[Path]], start: Path) -> List[List[Path]]:
            cycles = []
            visited = set()
            path = []
            
            def dfs(node: Path):
                if node in path:
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
                    return
                
                if node in visited:
                    return
                
                visited.add(node)
                path.append(node)
                
                if node in graph:
                    for neighbor in graph[node]:
                        dfs(neighbor)
                
                path.pop()
            
            dfs(start)
            return cycles
        
        # Build dependency graph
        graph = {
            header: set(self.analyzer.files[header].includes)
            for header in include_order
            if header in self.analyzer.files
        }
        
        return find_cycles(graph, file_path)
    
    def get_file_analysis(self, path: Path) -> Optional[FileIncludes]:
        """Gets analysis results for a specific file"""
        if self.project_analysis:
            return self.project_analysis.get_file_includes(path)
        return None
    
    def get_file_analysis_by_suffix(self, path: Path) -> Optional[FileIncludes]:
        if self.project_analysis:
            return self.project_analysis.get_file_includes_by_suffix(path)
        return None
    
    def get_include_suggestions(self, path: Path) -> Dict[str, any]:
        """Gets suggestions for fixing include issues in a file"""
        if not self.project_analysis:
            return {}
        
        file_analysis = self.project_analysis.get_file_includes(path)
        if not file_analysis:
            return {}
        
        return {
            "current_includes": list(map(str, file_analysis.include_order)),
            "missing_symbols": list(file_analysis.missing_symbols),
            "circular_dependencies": [
                list(map(str, cycle))
                for cycle in file_analysis.circular_dependencies
            ],
            "suggestions": {
                "add_includes": [
                    str(header)
                    for header in self._suggest_additional_includes(path)
                ],
                "remove_includes": [
                    str(header)
                    for header in self._suggest_removable_includes(path)
                ],
                "reorder_includes": self._suggest_include_reordering(path)
            }
        }
    
    def _suggest_additional_includes(self, path: Path) -> Set[Path]:
        """Suggests additional includes that might resolve missing symbols"""
        if not self.project_analysis:
            return set()
            
        file_analysis = self.project_analysis.get_file_includes(path)
        if not file_analysis or not file_analysis.missing_symbols:
            return set()
            
        suggestions = set()
        for symbol in file_analysis.missing_symbols:
            if symbol in self.project_analysis.symbol_registry:
                symbol_info = self.project_analysis.symbol_registry[symbol]
                if symbol_info.defined_in:
                    suggestions.add(symbol_info.defined_in)
        
        return suggestions
    
    def _suggest_removable_includes(self, path: Path) -> Set[Path]:
        """Suggests includes that might be unnecessary"""
        if not self.project_analysis:
            return set()
            
        file_analysis = self.project_analysis.get_file_includes(path)
        if not file_analysis:
            return set()
            
        removable = set()
        for include in file_analysis.direct_includes:
            # Check if all symbols from this include are available through other includes
            if include in self.analyzer.files:
                symbols_from_include = {
                    s.name for s in self.analyzer.files[include].definitions
                }
                other_includes = file_analysis.direct_includes - {include}
                available_symbols = self._get_available_symbols(
                    list(other_includes),
                    self.project_analysis.symbol_registry
                )
                if symbols_from_include.issubset(available_symbols):
                    removable.add(include)
        
        return removable
    
    def _suggest_include_reordering(self, path: Path) -> List[str]:
        """Suggests a better ordering of includes if possible"""
        if not self.project_analysis:
            return []
            
        file_analysis = self.project_analysis.get_file_includes(path)
        if not file_analysis:
            return []
            
        # Try to optimize the order based on symbol dependencies
        return [
            str(header)
            for header in self._determine_include_order(
                path,
                file_analysis.required_symbols,
                file_analysis.direct_includes,
                self.project_analysis.symbol_registry
            )
        ]