from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Tuple
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
class FileIncludeState:
    """Tracks the state of a file's include resolution"""
    path: Path
    provided_symbols: Set[str] = field(default_factory=set)
    required_symbols: Set[str] = field(default_factory=set)
    current_includes: List[Path] = field(default_factory=list)
    is_resolved: bool = False
    blocking_symbols: Set[str] = field(default_factory=set)
    dependent_files: Set[Path] = field(default_factory=set)

@dataclass
class ResolutionResult:
    """Result of attempting to resolve includes for a file"""
    success: bool
    include_order: List[Path]
    missing_symbols: Set[str]
    blocking_files: Set[Path]
    affected_files: Set[Path]

@dataclass
class DependencyNode:
    header: Path
    symbols_provided: Dict[str, SymbolContext]
    symbols_required: Dict[str, SymbolContext]
    direct_includes: Set[Path]
    indirect_includes: Set[Path] = field(default_factory=set)
    resolution_state: Optional[FileIncludeState] = None

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
        self.resolution_states: Dict[Path, FileIncludeState] = {}
        self.global_symbol_map: Dict[str, Set[Path]] = defaultdict(set)
        
        print("analyzeSources()")
        self.analyzeSources()

    def analyzeSources(self):
        project_paths = os.path.abspath(self.source_path)
        
        try:
            self.analyzer = analyzer = SourceAnalyzer([project_paths])
            analyzer.analyze()
            
            self._initialize_dependency_graph()
            self._build_global_symbol_map()
            self._resolve_all_dependencies()
            
        except Exception as e:
            print(f"Error during analysis: {e}")
            raise

    def _initialize_dependency_graph(self):
        """Initialize the dependency graph with basic file information"""
        # First pass: Create basic nodes
        for path, file in self.analyzer.files.items():
            if file.is_header:
                symbols_provided = self._analyze_symbol_contexts(file.definitions)
                symbols_required = self._analyze_symbol_contexts(file.usages)
                
                self.dependency_graph[path] = DependencyNode(
                    header=path,
                    symbols_provided=symbols_provided,
                    symbols_required=symbols_required,
                    direct_includes=set(file.includes)
                )
                
                # Initialize resolution state
                self.resolution_states[path] = FileIncludeState(
                    path=path,
                    provided_symbols={s for s in symbols_provided.keys()},
                    required_symbols={s for s in symbols_required.keys()}
                )

    def _build_global_symbol_map(self):
        """Build map of symbols to files that provide them"""
        for path, node in self.dependency_graph.items():
            for symbol in node.symbols_provided.keys():
                self.global_symbol_map[symbol].add(path)

    def _resolve_all_dependencies(self):
        """Resolve dependencies for all files iteratively"""
        changed = True
        iteration = 0
        max_iterations = len(self.dependency_graph) * 2  # Prevent infinite loops
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            print(f"\nIteration {iteration}")
            
            # Try to resolve each unresolved file
            for path, state in self.resolution_states.items():
                if not state.is_resolved:
                    result = self._try_resolve_file(path)
                    if result.success:
                        changed = True
                        self._update_resolution_state(path, result)
                        print(f"Resolved {path} with include order: {result.include_order}")
                    else:
                        print(f"Could not resolve {path}. Missing symbols: {result.missing_symbols}")
                        print(f"Blocking files: {result.blocking_files}")
            
            # Validate existing resolutions haven't been broken
            self._validate_existing_resolutions()

    def _try_resolve_file(self, file_path: Path) -> ResolutionResult:
        """Attempt to resolve dependencies for a single file"""
        state = self.resolution_states[file_path]
        required_symbols = state.required_symbols
        available_headers = set(self.dependency_graph.keys()) - {file_path}
        
        # Track files that might block resolution
        blocking_files = set()
        affected_files = {file_path}
        
        def get_available_symbols(headers: List[Path]) -> Set[str]:
            """Get all symbols available from a list of headers"""
            symbols = set()
            for h in headers:
                if h in self.resolution_states:
                    symbols.update(self.resolution_states[h].provided_symbols)
            return symbols
        
        def is_valid_include_order(order: List[Path]) -> bool:
            """Check if an include order is valid"""
            available = set()
            for header in order:
                state = self.resolution_states[header]
                # Check if header's required symbols are available
                missing = state.required_symbols - available
                if missing:
                    blocking_files.add(header)
                    return False
                available.update(state.provided_symbols)
            return True
        
        def find_minimal_include_order() -> Optional[List[Path]]:
            """Find minimal set of includes that provide all required symbols"""
            current_order = []
            remaining_symbols = set(required_symbols)
            used_headers = set()
            
            while remaining_symbols:
                best_header = None
                best_provided = set()
                
                # Find header that provides most remaining symbols
                for header in available_headers - used_headers:
                    if header in self.resolution_states:
                        provided = self.resolution_states[header].provided_symbols
                        useful_symbols = provided & remaining_symbols
                        if len(useful_symbols) > len(best_provided):
                            best_header = header
                            best_provided = useful_symbols
                
                if not best_header:
                    return None
                
                current_order.append(best_header)
                used_headers.add(best_header)
                remaining_symbols -= best_provided
                affected_files.add(best_header)
                
                # Validate current order
                if not is_valid_include_order(current_order):
                    return None
            
            return current_order

        # Try to find valid include order
        include_order = find_minimal_include_order()
        
        if include_order:
            return ResolutionResult(
                success=True,
                include_order=include_order,
                missing_symbols=set(),
                blocking_files=set(),
                affected_files=affected_files
            )
        else:
            # Determine missing symbols
            available = get_available_symbols(list(available_headers))
            missing = required_symbols - available
            
            return ResolutionResult(
                success=False,
                include_order=[],
                missing_symbols=missing,
                blocking_files=blocking_files,
                affected_files=affected_files
            )

    def _update_resolution_state(self, file_path: Path, result: ResolutionResult):
        """Update resolution state after successful dependency resolution"""
        state = self.resolution_states[file_path]
        state.is_resolved = True
        state.current_includes = result.include_order
        state.blocking_symbols.clear()
        
        # Update dependent files
        for affected in result.affected_files:
            if affected != file_path:
                self.resolution_states[affected].dependent_files.add(file_path)

    def _validate_existing_resolutions(self):
        """Validate that existing resolutions are still valid"""
        invalidated = set()
        
        for path, state in self.resolution_states.items():
            if state.is_resolved:
                # Check if current include order is still valid
                available_symbols = set()
                for inc in state.current_includes:
                    inc_state = self.resolution_states[inc]
                    available_symbols.update(inc_state.provided_symbols)
                
                if not state.required_symbols.issubset(available_symbols):
                    state.is_resolved = False
                    invalidated.add(path)
        
        if invalidated:
            print(f"Invalidated resolutions for: {invalidated}")
            # Invalidate dependent files
            for inv in invalidated:
                self._invalidate_dependents(inv)

    def _invalidate_dependents(self, file_path: Path):
        """Invalidate resolution state of all dependent files"""
        state = self.resolution_states[file_path]
        for dep in state.dependent_files:
            dep_state = self.resolution_states[dep]
            if dep_state.is_resolved:
                dep_state.is_resolved = False
                self._invalidate_dependents(dep)

    def _analyze_symbol_contexts(self, symbols: List[Symbol]) -> Dict[str, SymbolContext]:
        """Analyze the context of each symbol"""
        contexts = {}
        for sym in symbols:
            required = self._extract_required_symbols(sym.context)
            contexts[sym.name] = SymbolContext(sym.name, sym.kind, required)
        return contexts

    def _extract_required_symbols(self, context: str) -> Set[str]:
        """Extract required symbols from context"""
        symbols = set()
        words = re.findall(r'\b\w+\b', context)
        for word in words:
            if word in self.global_symbol_map:
                symbols.add(word)
        return symbols

    def verify_and_resolve(self) -> Dict[str, dict]:
        """Generate final verification and resolution report"""
        verification = IncludeVerification(
            missing_symbols=defaultdict(set),
            circular_refs=[],
            invalid_orders=[],
            suggested_fixes=[]
        )
        
        # Collect unresolved dependencies
        for path, state in self.resolution_states.items():
            if not state.is_resolved:
                verification.missing_symbols[str(path)] = state.blocking_symbols
                verification.invalid_orders.append({
                    'file': str(path),
                    'required_symbols': list(state.required_symbols)
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
                str(path): state.current_includes
                for path, state in self.resolution_states.items()
                if state.is_resolved
            }
        }

    def _find_circular_references(self) -> List[List[Path]]:
        """Find circular dependencies in the include hierarchy"""
        cycles = []
        visited = set()
        paths = []

        def dfs(node_path: Path):
            if node_path in paths:
                cycle_start = paths.index(node_path)
                cycles.append(paths[cycle_start:])
                return
            
            if node_path in visited:
                return
                
            visited.add(node_path)
            paths.append(node_path)
            
            if node_path in self.dependency_graph:
                node = self.dependency_graph[node_path]
                for inc in node.direct_includes:
                    dfs(inc)
                    
            paths.pop()

        for path in self.dependency_graph:
            if path not in visited:
                dfs(path)

        return cycles

    def _suggest_include_fixes(self, verification: IncludeVerification) -> List[dict]:
        """Get AI suggestions for resolving include problems"""
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
        
        resolution_status = {
            str(path): {
                "resolved": state.is_resolved,
                "current_includes": state.current_includes,
                "provided_symbols": list(state.provided_symbols),
                "required_symbols": list(state.required_symbols),
                "blocking_symbols": list(state.blocking_symbols)
            }
            for path, state in self.resolution_states.items()
        }
        
        prompt = f"""
        Detected problems:
        1. Missing symbols: {json.dumps(verification.missing_symbols)}
        2. Circular references: {verification.circular_refs}
        3. Invalid orders: {verification.invalid_orders}
        
        Current resolution status:
        {json.dumps(resolution_status, indent=2)}
        
        Suggest how to reorganize headers to resolve these issues while maintaining
        consistency across all files.
        """
        
        return self.ai_prompt(instruction, prompt)