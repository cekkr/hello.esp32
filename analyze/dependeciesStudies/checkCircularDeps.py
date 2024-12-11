from typing import Dict, List, Set, Tuple, Union, Any
from dataclasses import dataclass
from pathlib import Path
from dataclasses import is_dataclass, asdict

def convert_paths_to_strings(data: Union[Dict, Any]) -> Union[Dict, Any]:
    """
    Converte ricorsivamente tutti gli oggetti Path in stringhe all'interno di un dizionario,
    dei suoi sotto-dizionari e degli oggetti.

    Args:
        data: Un dizionario, un oggetto o un qualsiasi altro tipo di dato

    Returns:
        L'oggetto con tutti i Path convertiti in stringhe
    """
    # Se è un Path, convertilo in stringa
    if isinstance(data, Path):
        return str(data)

    # Se è un dizionario, elabora ricorsivamente ogni elemento
    if isinstance(data, dict):
        return {
            convert_paths_to_strings(key): convert_paths_to_strings(value)
            for key, value in data.items()
        }

    # Se è una lista o una tupla, elabora ricorsivamente ogni elemento
    if isinstance(data, (list, tuple)):
        return type(data)(convert_paths_to_strings(item) for item in data)

    # Se è un dataclass, convertilo in dizionario e poi elaboralo
    if is_dataclass(data):
        return convert_paths_to_strings(asdict(data))

    # Se è un oggetto generico con __dict__, elabora i suoi attributi
    if hasattr(data, '__dict__'):
        # Creiamo una copia dell'oggetto per non modificare l'originale
        import copy
        obj_copy = copy.copy(data)

        # Convertiamo gli attributi
        for key, value in vars(data).items():
            setattr(obj_copy, key, convert_paths_to_strings(value))
        return obj_copy

    # Per tutti gli altri tipi di dati, restituisci il valore invariato
    return data

@dataclass
class FileInfo:
    includes: List[str]


class SelfInclusionError(Exception):
    def __init__(self, file: str):
        self.file = file
        super().__init__(f"Self-inclusion detected in file: {file}")


class CircularDependencyError(Exception):
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(f"Trovata dipendenza circolare: {cycle_str}")


class HeaderDependencyOptimizer:
    def __init__(self, files: Dict[str, FileInfo]):
        self.files = files
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.optimized_includes: Dict[str, List[str]] = {}

    def check_self_inclusions(self):
        """Verifica la presenza di auto-inclusioni nei file."""
        for file_name, file_info in self.files.items():
            if file_name in file_info['includes']:
                #raise SelfInclusionError(file_name)
                file_info['includes'].remove(file_name)

    def build_dependency_graph(self):
        """Costruisce il grafo delle dipendenze dirette e transitive."""
        # Prima verifichiamo le auto-inclusioni
        self.check_self_inclusions()

        # Inizializza il grafo con le dipendenze dirette, escludendo auto-inclusioni
        for file_name, file_info in self.files.items():
            self.dependency_graph[file_name] = {
                inc for inc in file_info['includes']
                if inc != file_name  # Escludiamo esplicitamente le auto-inclusioni
            }

        # Calcola le dipendenze transitive
        changed = True
        while changed:
            changed = False
            for file_name in self.files:
                current_deps = self.dependency_graph[file_name].copy()
                for dep in current_deps:
                    if dep in self.dependency_graph:
                        if file_name not in self.dependency_graph[dep]:
                            new_deps = self.dependency_graph[dep] - current_deps
                            if new_deps:
                                self.dependency_graph[file_name].update(new_deps)
                                changed = True

    def check_circular_dependencies(self) -> List[List[str]]:
        """Identifica eventuali dipendenze circolari."""
        circular_deps = []
        visited = set()

        def dfs(file: str, path: List[str]):
            if file in path:
                cycle_start = path.index(file)
                cycle = path[cycle_start:]
                cycle.append(file)
                circular_deps.append(cycle)
                return

            path.append(file)
            if file in self.dependency_graph:
                for dep in self.dependency_graph[file]:
                    if dep not in visited:
                        new_path = path.copy()
                        dfs(dep, new_path)
            visited.add(file)

        for file in self.files:
            if file not in visited:
                dfs(file, [])

        return circular_deps

    def optimize_includes(self, break_cycles: bool = False) -> Dict[str, List[str]]:
        """Ottimizza gli #include per ogni file."""
        try:
            self.build_dependency_graph()
        except SelfInclusionError as e:
            print(f"ERRORE: {e}")
            print("Rimuovo l'auto-inclusione e continuo...")
            # Rimuovi l'auto-inclusione dal file originale
            self.files[e.file]['includes'] = [
                inc for inc in self.files[e.file]['includes']
                if inc != e.file
            ]
            # Ricostruisci il grafo
            self.build_dependency_graph()

        circular_deps = self.check_circular_dependencies()
        if circular_deps:
            if not break_cycles:
                raise CircularDependencyError(circular_deps[0])
            else:
                for cycle in circular_deps:
                    source = cycle[-2]
                    target = cycle[-1]
                    self.dependency_graph[source].remove(target)
                    print(f"WARNING: Rotto il ciclo rimuovendo la dipendenza {source} -> {target}")

        for file_name, file_info in self.files.items():
            necessary_includes = set(inc for inc in file_info['includes'] if inc != file_name)
            for include in file_info['includes']:
                if include in self.dependency_graph and include != file_name:
                    necessary_includes -= self.dependency_graph[include]
            self.optimized_includes[file_name] = sorted(list(necessary_includes))

        return self.optimized_includes

    def generate_include_statements(self, break_cycles: bool = False) -> Dict[str, str]:
        """Genera gli statement #include formattati per ogni file."""
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