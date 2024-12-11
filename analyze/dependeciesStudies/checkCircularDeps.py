from typing import Dict, List, Set, Tuple
from dataclasses import dataclass


@dataclass
class FileInfo:
    includes: List[str]
    # Altri campi potrebbero essere aggiunti qui, come simboli_definiti, simboli_usati, etc.

class CircularDependencyError(Exception):
    def __init__(self, cycle: Tuple[str, ...]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(f"Trovata dipendenza circolare: {cycle_str}")

class HeaderDependencyOptimizer:
    def __init__(self, files: Dict[str, FileInfo]):
        self.files = files
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.optimized_includes: Dict[str, List[str]] = {}

    def build_dependency_graph(self):
        """Costruisce il grafo delle dipendenze dirette e transitive."""
        # Inizializza il grafo con le dipendenze dirette
        for file_name, file_info in self.files.items():
            self.dependency_graph[file_name] = set(file_info.includes)

        # Calcola le dipendenze transitive
        changed = True
        while changed:
            changed = False
            for file_name in self.files:
                current_deps = self.dependency_graph[file_name].copy()
                for dep in current_deps:
                    if dep in self.dependency_graph:
                        # Non includiamo le dipendenze che ci includono
                        if file_name not in self.dependency_graph[dep]:
                            new_deps = self.dependency_graph[dep] - current_deps
                            if new_deps:
                                self.dependency_graph[file_name].update(new_deps)
                                changed = True

    def check_circular_dependencies(self) -> List[Tuple[str, ...]]:
        """Identifica eventuali dipendenze circolari."""
        circular_deps = []
        visited = set()

        def dfs(file: str, path: List[str]):
            if file in path:
                cycle_start = path.index(file)
                circular_deps.append(tuple(path[cycle_start:] + [file]))
                return

            path.append(file)
            if file in self.dependency_graph:
                for dep in self.dependency_graph[file]:
                    if dep not in visited:
                        dfs(dep, path.copy())
            visited.add(file)

        for file in self.files:
            if file not in visited:
                dfs(file, [])

        return circular_deps

    def optimize_includes(self, break_cycles: bool = False) -> Dict[str, List[str]]:
        """
        Ottimizza gli #include per ogni file.

        Args:
            break_cycles: Se True, tenta di risolvere le dipendenze circolari rimuovendo
                        l'inclusione meno necessaria. Se False, solleva un'eccezione.

        Raises:
            CircularDependencyError: Se vengono trovate dipendenze circolari e break_cycles è False.
        """
        self.build_dependency_graph()

        # Controlla le dipendenze circolari
        circular_deps = self.check_circular_dependencies()
        if circular_deps:
            if not break_cycles:
                raise CircularDependencyError(circular_deps[0])
            else:
                # Rompi i cicli rimuovendo la dipendenza meno necessaria
                for cycle in circular_deps:
                    # Per semplicità, rimuoviamo l'ultima dipendenza nel ciclo
                    # In un caso reale, potremmo usare euristiche più sofisticate
                    source = cycle[-2]
                    target = cycle[-1]
                    self.dependency_graph[source].remove(target)
                    print(f"WARNING: Rotto il ciclo rimuovendo la dipendenza {source} -> {target}")

        for file_name, file_info in self.files.items():
            # Inizia con tutte le dipendenze dirette
            necessary_includes = set(file_info.includes)

            # Rimuovi le inclusioni ridondanti
            for include in file_info.includes:
                if include in self.dependency_graph:
                    necessary_includes -= self.dependency_graph[include]

            # Ordina gli include per leggibilità
            self.optimized_includes[file_name] = sorted(list(necessary_includes))

        return self.optimized_includes

    def generate_include_statements(self, break_cycles: bool = False) -> Dict[str, str]:
        """
        Genera gli statement #include formattati per ogni file.

        Args:
            break_cycles: Se True, tenta di risolvere le dipendenze circolari rimuovendo
                        l'inclusione meno necessaria. Se False, solleva un'eccezione.
        """
        self.optimize_includes(break_cycles)
        include_statements = {}

        for file_name, includes in self.optimized_includes.items():
            statements = []
            for include in includes:
                if include.endswith(('.h', '.hpp')):
                    statements.append(f'#include "{include}"')
            include_statements[file_name] = '\n'.join(statements)

        return include_statements

'''
# Esempio di utilizzo
files = {
    'main.c': FileInfo(includes=['utils.h', 'config.h']),
    'utils.h': FileInfo(includes=['config.h', 'types.h']),
    'config.h': FileInfo(includes=['types.h']),
    'types.h': FileInfo(includes=[])
}

optimizer = HeaderDependencyOptimizer(files)

# Ottimizza gli include
optimized = optimizer.generate_include_statements()

# Verifica eventuali dipendenze circolari
circular = optimizer.check_circular_dependencies()

# Stampa i risultati
for file_name, includes in optimized.items():
    print(f"\n{file_name}:")
    print(includes)
'''

'''
files = {
    'a.h': FileInfo(includes=['b.h']),
    'b.h': FileInfo(includes=['c.h']),
    'c.h': FileInfo(includes=['a.h'])  # Crea un ciclo
}

optimizer = HeaderDependencyOptimizer(files)
try:
    optimized = optimizer.generate_include_statements()
except CircularDependencyError as e:
    print(f"Errore: {e}")
    # Qui puoi gestire l'errore, per esempio:
    # - Segnalarlo agli sviluppatori
    # - Loggarlo
    # - Terminare il build process
    
# automatic
optimizer = HeaderDependencyOptimizer(files)
optimized = optimizer.generate_include_statements(break_cycles=True)
# Stamperà un warning per ogni ciclo rotto
'''