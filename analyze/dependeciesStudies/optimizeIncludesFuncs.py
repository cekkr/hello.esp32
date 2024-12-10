from typing import Dict, Set, List, Optional
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
from includeManager import ResolutionResult, DependencyNode, IncludeVerification
from readCLib import SourceFile

def optimize_includes(source_files: Dict[Path, SourceFile]) -> Dict[Path, ResolutionResult]:
    """
    Ottimizza l'ordine delle inclusioni per un insieme di file C/C++.

    Args:
        source_files: Dizionario di file sorgente indicizzati per percorso

    Returns:
        Dizionario di ResultResolution per ogni file
    """
    results = {}
    dependency_graph = build_dependency_graph(source_files)

    for file_path, source_file in source_files.items():
        if not source_file.is_header:
            continue

        resolution = resolve_includes_for_file(file_path, dependency_graph, source_files)
        results[file_path] = resolution

    return results


def build_dependency_graph(source_files: Dict[Path, SourceFile]) -> Dict[Path, DependencyNode]:
    """
    Costruisce il grafo delle dipendenze tra i file.
    """
    graph = {}

    for path, source_file in source_files.items():
        symbols_provided = {}
        symbols_required = {}

        # Registra i simboli forniti
        for symbol in source_file.definitions:
            context = SymbolContext(
                name=symbol.name,
                kind=symbol.kind,
                required_symbols=set()  # Sarà popolato successivamente
            )
            symbols_provided[symbol.name] = context

        # Registra i simboli richiesti
        for usage in source_file.usages:
            if usage.name not in symbols_required:
                context = SymbolContext(
                    name=usage.name,
                    kind=usage.kind,
                    required_symbols=set()
                )
                symbols_required[usage.name] = context

        graph[path] = DependencyNode(
            header=path,
            symbols_provided=symbols_provided,
            symbols_required=symbols_required,
            direct_includes=set(source_file.includes),
            resolution_state=FileIncludeState(path=path)
        )

    return graph


def resolve_includes_for_file(
        file_path: Path,
        dependency_graph: Dict[Path, DependencyNode],
        source_files: Dict[Path, SourceFile]
) -> ResolutionResult:
    """
    Risolve l'ordine ottimale delle inclusioni per un singolo file.
    """
    visited = set()
    include_order = []
    missing_symbols = set()
    blocking_files = set()
    affected_files = set()

    def resolve_recursive(current_path: Path, available_symbols: Set[str]) -> bool:
        if current_path in visited:
            return True

        visited.add(current_path)
        node = dependency_graph[current_path]
        current_file = source_files[current_path]

        # Verifica i simboli richiesti
        needed_symbols = {symbol.name for symbol in current_file.usages}
        missing = needed_symbols - available_symbols

        if missing:
            # Cerca i file che forniscono i simboli mancanti
            for symbol in missing:
                found = False
                for include_path in current_file.includes:
                    include_node = dependency_graph[include_path]
                    if symbol in include_node.symbols_provided:
                        if resolve_recursive(include_path, available_symbols):
                            found = True
                            break
                if not found:
                    missing_symbols.add(symbol)

        # Aggiungi i simboli forniti da questo file
        available_symbols.update(symbol.name for symbol in current_file.definitions)
        include_order.append(current_path)

        return True

    initial_symbols = set()
    resolve_recursive(file_path, initial_symbols)

    # Rimuovi il file corrente dall'ordine delle inclusioni
    if file_path in include_order:
        include_order.remove(file_path)

    return ResolutionResult(
        success=len(missing_symbols) == 0,
        include_order=include_order,
        missing_symbols=missing_symbols,
        blocking_files=blocking_files,
        affected_files=affected_files
    )


def validate_include_order(
        file_path: Path,
        include_order: List[Path],
        dependency_graph: Dict[Path, DependencyNode]
) -> IncludeVerification:
    """
    Valida l'ordine delle inclusioni proposto e suggerisce correzioni.
    """
    missing_symbols = defaultdict(set)
    circular_refs = []
    invalid_orders = []
    suggested_fixes = []

    available_symbols = set()
    symbol_providers = {}

    for include_path in include_order:
        node = dependency_graph[include_path]

        # Verifica che tutti i simboli richiesti siano disponibili
        for symbol in node.symbols_required:
            if symbol not in available_symbols:
                missing_symbols[include_path].add(symbol)

                # Cerca possibili provider per il simbolo mancante
                for other_path, other_node in dependency_graph.items():
                    if symbol in other_node.symbols_provided:
                        suggested_fixes.append({
                            'file': include_path,
                            'missing_symbol': symbol,
                            'potential_provider': other_path
                        })

        # Aggiorna i simboli disponibili
        available_symbols.update(node.symbols_provided.keys())

        # Registra i provider dei simboli
        for symbol in node.symbols_provided:
            if symbol in symbol_providers:
                invalid_orders.append({
                    'symbol': symbol,
                    'providers': [str(symbol_providers[symbol]), str(include_path)]
                })
            symbol_providers[symbol] = include_path

    return IncludeVerification(
        missing_symbols=dict(missing_symbols),
        circular_refs=circular_refs,
        invalid_orders=invalid_orders,
        suggested_fixes=suggested_fixes
    )