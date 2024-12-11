from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class FileInfo:
    includes: List[str]
    # Altri campi potrebbero essere aggiunti qui, come simboli_definiti, simboli_usati, etc.


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

    def optimize_includes(self) -> Dict[str, List[str]]:
        """Ottimizza gli #include per ogni file."""
        self.build_dependency_graph()

        for file_name, file_info in self.files.items():
            # Inizia con tutte le dipendenze dirette
            necessary_includes = set(file_info.includes)

            # Rimuovi le inclusioni ridondanti
            for include in file_info.includes:
                # Se un file A include B e C, ma B include già C,
                # allora A non ha bisogno di includere C direttamente
                if include in self.dependency_graph:
                    necessary_includes -= self.dependency_graph[include]

            # Ordina gli include per leggibilità
            self.optimized_includes[file_name] = sorted(list(necessary_includes))

        return self.optimized_includes

    def generate_include_statements(self) -> Dict[str, str]:
        """Genera gli statement #include formattati per ogni file."""
        self.optimize_includes()
        include_statements = {}

        for file_name, includes in self.optimized_includes.items():
            statements = []
            for include in includes:
                if include.endswith(('.h', '.hpp')):
                    statements.append(f'#include "{include}"')
            include_statements[file_name] = '\n'.join(statements)

        return include_statements

    def check_circular_dependencies(self) -> List[tuple]:
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