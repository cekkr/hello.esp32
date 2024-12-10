from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
from collections import defaultdict
import json
import re
from readCLib import *

@dataclass
class SymbolContext:
    name: str
    kind: str
    required_symbols: Set[str]

@dataclass
class FileIncludeOrder:
    file_path: Path
    direct_includes: Set[Path]
    required_symbols: Set[str]
    provided_symbols: Set[str]
    optimal_include_order: List[Path] = field(default_factory=list)
    missing_symbols: Set[str] = field(default_factory=set)
    cyclic_dependencies: List[List[Path]] = field(default_factory=list)

@dataclass
class HeaderFile:
    path: Path
    symbols_provided: Dict[str, SymbolContext]
    symbols_required: Dict[str, SymbolContext]
    direct_includes: Set[Path]
    indirect_includes: Set[Path] = field(default_factory=set)
    dependents: Set[Path] = field(default_factory=set)
    include_order: Optional[FileIncludeOrder] = None

@dataclass
class SourceFile:
    path: Path
    required_symbols: Set[str]
    direct_includes: Set[Path]
    include_order: Optional[FileIncludeOrder] = None

@dataclass
class DependencyNode:
    header: Path
    symbols_provided: Dict[str, SymbolContext]
    symbols_required: Dict[str, SymbolContext]
    direct_includes: Set[Path]
    indirect_includes: Set[Path] = field(default_factory=set)

    def get_available_symbols(self, include_chain: List[Path]) -> Set[str]:
        symbols = set()
        for header in include_chain:
            if header == self.header:
                break
            if header in self.symbols_provided:
                symbols.update(self.symbols_provided[header].keys())
        return symbols

@dataclass
class IncludeVerification:
    missing_symbols: Dict[str, Set[str]]
    circular_refs: List[List[Path]]
    invalid_orders: List[Dict[str, List[str]]]
    suggested_fixes: List[dict]

@dataclass
class IncludeResolver:
    source_files: Dict[Path, SourceFile]
    ai_prompt: Callable[[str, str], dict]
    
    def __init__(self, sources_path: str, ai_prompt_call: Callable[[str, str], dict]):
        self.ai_prompt = ai_prompt_call
        self.source_path = sources_path
        self.analyzer = None
        self.dependency_graph: Dict[Path, DependencyNode] = {}
        self.symbol_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.header_files: Dict[Path, HeaderFile] = {}
        self.source_files: Dict[Path, SourceFile] = {}
        self.file_include_orders: Dict[Path, FileIncludeOrder] = {}
        
        print("analyzeSources()")
        self.analyzeSources()

    def analyzeSources(self):
        project_paths = os.path.abspath(self.source_path)
        
        try:
            self.analyzer = analyzer = SourceAnalyzer(project_paths)
            analyzer.analyze()
            
            # Convert analyzed data to our enhanced structure
            self._build_file_structures()
            self._calculate_include_orders()
            
            if True:  # Debug printing
                self._print_analysis_results()
                
        except Exception as e:
            print(f"Error during analysis: {e}")
            raise

    def _build_file_structures(self):
        """Builds header and source file structures from analyzer data"""
        # First pass: Create basic file structures
        for path, source_file in self.analyzer.files.items():
            if source_file.is_header:
                symbols_provided = self._analyze_symbol_contexts(source_file.definitions)
                symbols_required = self._analyze_symbol_contexts(source_file.usages)
                
                self.header_files[path] = HeaderFile(
                    path=path,
                    symbols_provided=symbols_provided,
                    symbols_required=symbols_required,
                    direct_includes=set(source_file.includes)
                )
            else:
                self.source_files[path] = SourceFile(
                    path=path,
                    required_symbols={s.name for s in source_file.usages},
                    direct_includes=set(source_file.includes)
                )

        # Second pass: Calculate indirect includes and dependencies
        self._calculate_indirect_includes()
        self._build_dependency_graph()

    def _calculate_indirect_includes(self):
        """Calculates indirect includes for all header files"""
        changed = True
        while changed:
            changed = False
            for header in self.header_files.values():
                old_size = len(header.indirect_includes)
                
                for inc in header.direct_includes:
                    if inc in self.header_files:
                        inc_header = self.header_files[inc]
                        header.indirect_includes.update(inc_header.direct_includes)
                        header.indirect_includes.update(inc_header.indirect_includes)
                
                if len(header.indirect_includes) > old_size:
                    changed = True

    def _calculate_include_orders(self):
        """Calculates optimal include orders for all files"""
        # Calculate for header files
        for header in self.header_files.values():
            include_order = self._calculate_file_include_order(
                header.path,
                header.symbols_required.keys(),
                set(self.header_files.keys()) - {header.path}
            )
            header.include_order = include_order
            self.file_include_orders[header.path] = include_order

        # Calculate for source files
        for source in self.source_files.values():
            include_order = self._calculate_file_include_order(
                source.path,
                source.required_symbols,
                set(self.header_files.keys())
            )
            source.include_order = include_order
            self.file_include_orders[source.path] = include_order

    def _calculate_file_include_order(
        self,
        file_path: Path,
        required_symbols: Set[str],
        available_headers: Set[Path]
    ) -> FileIncludeOrder:
        """Calculates optimal include order for a specific file"""
        direct_includes = (self.header_files[file_path].direct_includes 
                         if file_path in self.header_files 
                         else self.source_files[file_path].direct_includes)
        
        include_order = FileIncludeOrder(
            file_path=file_path,
            direct_includes=direct_includes,
            required_symbols=set(required_symbols),
            provided_symbols=set()
        )

        # Try to find optimal include order
        ordered_includes = self._find_valid_include_order(
            required_symbols,
            available_headers
        )

        if ordered_includes:
            include_order.optimal_include_order = ordered_includes
            # Calculate provided symbols from this order
            for header in ordered_includes:
                if header in self.header_files:
                    include_order.provided_symbols.update(
                        self.header_files[header].symbols_provided.keys()
                    )
        else:
            # If no valid order found, calculate missing symbols
            available_symbols = set()
            for header in available_headers:
                if header in self.header_files:
                    available_symbols.update(
                        self.header_files[header].symbols_provided.keys()
                    )
            include_order.missing_symbols = required_symbols - available_symbols

        return include_order

    def _analyze_symbol_contexts(self, symbols: List[Symbol]) -> Dict[str, SymbolContext]:
        """Analyzes the context of each symbol"""
        contexts = {}
        for sym in symbols:
            required = self._extract_required_symbols(sym.context)
            contexts[sym.name] = SymbolContext(sym.name, sym.kind, required)
        return contexts

    def _extract_required_symbols(self, context: str) -> Set[str]:
        """Extracts required symbols from context"""
        symbols = set()
        words = re.findall(r'\b\w+\b', context)
        for word in words:
            if word in self.symbol_dependencies:
                symbols.add(word)
        return symbols

    def _build_dependency_graph(self):
        """Builds dependency graph from file structures"""
        for path, header in self.header_files.items():
            self.dependency_graph[path] = DependencyNode(
                header=path,
                symbols_provided=header.symbols_provided,
                symbols_required=header.symbols_required,
                direct_includes=header.direct_includes,
                indirect_includes=header.indirect_includes
            )

    def _find_valid_include_order(
        self,
        required_symbols: Set[str],
        available_headers: Set[Path]
    ) -> Optional[List[Path]]:
        """Finds valid include order to obtain all required symbols"""
        def try_order(
            current_order: List[Path],
            remaining_symbols: Set[str],
            used_headers: Set[Path]
        ) -> Optional[List[Path]]:
            if not remaining_symbols:
                return current_order
            
            for header in available_headers - used_headers:
                if header not in self.header_files:
                    continue
                    
                provided = set(self.header_files[header].symbols_provided.keys())
                if provided & remaining_symbols:
                    new_order = current_order + [header]
                    new_remaining = remaining_symbols - provided
                    
                    if self._verify_include_chain(new_order):
                        result = try_order(
                            new_order,
                            new_remaining,
                            used_headers | {header}
                        )
                        if result:
                            return result
            return None

        return try_order([], required_symbols, set())

    def _verify_include_chain(self, include_chain: List[Path]) -> bool:
        """Verifies that an include chain is valid"""
        available_symbols = set()
        
        for header in include_chain:
            if header not in self.header_files:
                continue
                
            current_header = self.header_files[header]
            
            # Check that required symbols are available
            for symbol in current_header.symbols_required:
                if symbol not in available_symbols:
                    return False
            
            # Update available symbols
            available_symbols.update(current_header.symbols_provided.keys())
            
        return True

    def verify_and_resolve(self) -> Dict[str, dict]:
        """Verifies and resolves include problems"""
        verification = IncludeVerification(
            missing_symbols=defaultdict(set),
            circular_refs=[],
            invalid_orders=[],
            suggested_fixes=[]
        )
        
        # Check each file's include order
        for path, include_order in self.file_include_orders.items():
            if include_order.missing_symbols:
                verification.missing_symbols[str(path)] = include_order.missing_symbols
            
            if not include_order.optimal_include_order:
                verification.invalid_orders.append({
                    'file': str(path),
                    'required_symbols': list(include_order.required_symbols)
                })
        
        # Find circular references
        verification.circular_refs = self._find_circular_references()
        
        # Get AI suggestions if there are problems
        if verification.missing_symbols or verification.invalid_orders:
            fixes = self._suggest_include_fixes(verification)
            verification.suggested_fixes.extend(fixes)
        
        return {
            'verification': {
                'missing_symbols': dict(verification.missing_symbols),
                'circular_refs': verification.circular_refs,
                'invalid_orders': verification.invalid_orders
            },
            'fixes': verification.suggested_fixes,
            'include_orders': {
                str(path): order.optimal_include_order
                for path, order in self.file_include_orders.items()
            }
        }

    def _find_circular_references(self) -> List[List[Path]]:
        """Finds circular references in the include hierarchy"""
        cycles = []
        visited = set()
        path = []

        def dfs(header: Path):
            if header in path:
                cycle_start = path.index(header)
                cycles.append(path[cycle_start:])
                return
            
            if header in visited:
                return
                
            visited.add(header)
            path.append(header)
            
            if header in self.header_files:
                for inc in self.header_files[header].direct_includes:
                    dfs(inc)
                    
            path.pop()

        for header in self.header_files:
            if header not in visited:
                dfs(header)

        return cycles

    def _suggest_include_fixes(self, verification: IncludeVerification) -> List[dict]:
        """Asks AI for suggestions to resolve include problems"""
        instruction = """
        Analyze include problems and suggest solutions.
        Expected JSON format:
        {
            "new_headers": [
                {
                    "name": string,
                    "symbols": [string],
                    "reason": string
                }
            ],
            "moved_symbols": [
                {
                    "symbol": string,
                    "from": string,
                    "to": string,
                    "reason": string
                }
            ],
            "include_order_fixes": [
                {
                    "file": string,
                    "current_order": [string],
                    "suggested_order": [string],
                    "reason": string
                }
            ]
        }
        """
        
        prompt = f"""
        Detected problems:
        1. Missing symbols: {json.dumps(verification.missing_symbols)}
        2. Circular references: {verification.circular_refs}
        3. Invalid orders: {verification.invalid_orders}
        
        For each header, defined symbols:
        {json.dumps({str(k): list(v.symbols_provided.keys()) 
                    for k,v in self.header_files.items()}, indent=2)}
        
        Suggest how to reorganize headers to resolve these issues.
        """
        
        return self.ai_prompt(instruction, prompt)

    def _print_analysis_results(self):
        """Prints analysis results for debugging"""
        print("\nAnalysis Results:")
        print("\nHeader Files:")
        for path, header in self.header_files.items():
            print(f"\n{path}:")
            print(f"Provided symbols: {list(header.symbols_provided.keys())}")
            print(f"Required symbols: {list(header.symbols_required.keys())}")
            if header.include_order:
                print(f"Optimal include order: {header.include_order.optimal_include_order}")
                print(f"Missing symbols: {header.include_order.missing_symbols}")

        print("\nSource Files:")
        for path, source in self.source_files.items():
            print(f"\n{path}:")
            print(f"Required symbols: {source.required_symbols}")
            if source.include_order:
                print(f"Optimal include order: {source.include_order.optimal_include_order}")
                print(f"Missing symbols: {source.include_order.missing_symbols}")