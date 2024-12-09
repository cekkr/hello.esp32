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
    required_symbols: Set[str]  # Simboli necessari per definire questo simbolo

@dataclass
class DependencyNode:
    header: Path
    symbols_provided: Dict[str, SymbolContext]  # Simboli definiti con il loro contesto
    symbols_required: Dict[str, SymbolContext]  # Simboli necessari con il loro contesto
    direct_includes: Set[Path]
    indirect_includes: Set[Path] = field(default_factory=set)
    
    def get_available_symbols(self, include_chain: List[Path]) -> Set[str]:
        """Calcola i simboli disponibili considerando la catena di inclusione"""
        symbols = set()
        for idx, header in enumerate(include_chain):
            # Controlla che i simboli necessari siano già disponibili
            if header == self.header:
                break
            symbols.update(self.symbols_provided[header].keys())
        return symbols

@dataclass
class IncludeVerification:
    missing_symbols: Dict[str, Set[str]]  # File -> simboli mancanti
    circular_refs: List[List[Path]]
    invalid_orders: List[Dict[str, List[str]]]  # Ordini di inclusione non validi
    suggested_fixes: List[dict]

@dataclass
class IncludeResolver:
    source_files: Dict[Path, SourceFile]
    ai_prompt: Callable[[str, str], dict]
    
    def __init__(self, sources_path, ai_prompt_call):
        self.ai_prompt = ai_prompt_call
        self.source_path = sources_path
        self.analyzer = None

    def __post_init__(self):
        self.dependency_graph: Dict[Path, DependencyNode] = {}
        self.symbol_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._build_dependency_graph()
        self._analyze_symbol_dependencies()

    def analyzeSources(self):
        project_paths = os.path.abspath(self.source_path)
        
        try:
            self.analyzer = analyzer = SourceAnalyzer(project_paths)
            print("Analisi del progetto in corso...")
            analyzer.analyze()
            
            printAndDive = True
            if printAndDive:
                analyzer.print_dependencies()
                analyzer.print_symbols()
                analyzer.find_cycles()
                analyzer.suggest_missing_includes()
                
                # Opzionale: analisi dettagliata di simboli specifici
                while True:
                    symbol = input("\nInserisci il nome di un simbolo da analizzare (o premi Invio per terminare): ")
                    if not symbol:
                        break
                    analyzer.analyze_symbol(symbol)
            else:
                pass # analyze dependencies
        
        except Exception as e:
            print(f"Errore durante l'analisi: {e}")
            raise

    def _build_dependency_graph(self):
        """Costruisce il grafo delle dipendenze con contesto dei simboli"""
        for path, sf in self.source_files.items():
            if sf.is_header:
                node = DependencyNode(
                    header=path,
                    symbols_provided=self._analyze_symbol_contexts(sf.definitions),
                    symbols_required=self._analyze_symbol_contexts(sf.usages),
                    direct_includes=set(sf.includes)
                )
                self.dependency_graph[path] = node

    def _analyze_symbol_contexts(self, symbols: List[Symbol]) -> Dict[str, SymbolContext]:
        """Analizza il contesto di ogni simbolo"""
        contexts = {}
        for sym in symbols:
            required = self._extract_required_symbols(sym.context)
            contexts[sym.name] = SymbolContext(sym.name, sym.kind, required)
        return contexts

    def _extract_required_symbols(self, context: str) -> Set[str]:
        """Estrae i simboli necessari dal contesto (es. struct, typedef)"""
        # Implementazione semplificata - potrebbe essere espansa con analisi più dettagliata
        symbols = set()
        words = re.findall(r'\b\w+\b', context)
        for word in words:
            if word in self.symbol_dependencies:
                symbols.add(word)
        return symbols

    def _verify_include_chain(self, file: Path, chain: List[Path]) -> List[str]:
        """Verifica che una catena di inclusioni sia valida"""
        errors = []
        available_symbols = set()
        
        for idx, header in enumerate(chain):
            node = self.dependency_graph[header]
            current_symbols = set(node.symbols_provided.keys())
            
            # Verifica che i simboli necessari siano disponibili
            for symbol, context in node.symbols_required.items():
                required = context.required_symbols
                missing = required - available_symbols
                if missing:
                    errors.append(f"Header {header}: simboli mancanti per {symbol}: {missing}")
            
            # Aggiorna i simboli disponibili
            available_symbols.update(current_symbols)
            
            # Verifica dipendenze ricorsive
            if idx > 0:
                prev_headers = chain[:idx]
                if any(ph in node.all_includes for ph in prev_headers):
                    errors.append(f"Dipendenza circolare rilevata in {header}")

        return errors

    def _find_valid_include_order(self, required_symbols: Set[str], available_headers: Set[Path]) -> Optional[List[Path]]:
        """Trova un ordine valido di inclusione per ottenere tutti i simboli necessari"""
        def try_order(current_order: List[Path], remaining_symbols: Set[str], used_headers: Set[Path]) -> Optional[List[Path]]:
            if not remaining_symbols:
                return current_order
            
            for header in available_headers - used_headers:
                node = self.dependency_graph[header]
                provided = set(node.symbols_provided.keys())
                if provided & remaining_symbols:
                    new_order = current_order + [header]
                    if not self._verify_include_chain(None, new_order):  # No errors
                        result = try_order(
                            new_order,
                            remaining_symbols - provided,
                            used_headers | {header}
                        )
                        if result:
                            return result
            return None

        return try_order([], required_symbols, set())

    def _suggest_include_fixes(self, verification: IncludeVerification) -> List[dict]:
        """Chiede all'AI suggerimenti per risolvere i problemi di inclusione"""
        instruction = """
        Analizza i problemi di inclusione e suggerisci soluzioni.
        Formato JSON atteso:
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
        Problemi rilevati:
        1. Simboli mancanti: {json.dumps(verification.missing_symbols)}
        2. Riferimenti circolari: {verification.circular_refs}
        3. Ordini non validi: {verification.invalid_orders}
        
        Per ogni header, simboli definiti:
        {json.dumps({str(k): list(v.symbols_provided.keys()) for k,v in self.dependency_graph.items()}, indent=2)}
        
        Suggerisci come riorganizzare gli header per risolvere questi problemi.
        """
        
        return self.ai_prompt(instruction, prompt)

    def verify_and_resolve(self) -> Dict[str, dict]:
        """Verifica e risolve i problemi di inclusione"""
        verification = IncludeVerification(
            missing_symbols=defaultdict(set),
            circular_refs=[],
            invalid_orders=[],
            suggested_fixes=[]
        )
        
        # Verifica ogni file
        for path, file in self.source_files.items():
            if not file.is_header:
                required = {s.name for s in file.usages}
                current_order = self._find_valid_include_order(required, set(self.dependency_graph.keys()))
                
                if not current_order:
                    verification.invalid_orders.append({
                        'file': str(path),
                        'required_symbols': list(required)
                    })
                
                errors = self._verify_include_chain(path, current_order or [])
                if errors:
                    verification.missing_symbols[str(path)].update(errors)
        
        # Richiedi suggerimenti all'AI
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
                str(path): self._find_valid_include_order(
                    {s.name for s in file.usages},
                    set(self.dependency_graph.keys())
                )
                for path, file in self.source_files.items()
                if not file.is_header
            }
        }