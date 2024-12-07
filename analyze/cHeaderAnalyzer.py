import re
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, Set, List, Tuple

class HeaderAnalyzer:
    def __init__(self):
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.processed_files = set()
        self.undefined_symbols = defaultdict(set)
        self.symbol_definitions = defaultdict(set)

    def parse_build_log(self, log_content: str) -> None:
        """Analizza il log di build per estrarre le inclusioni e gli errori."""
        current_file = None
        include_pattern = re.compile(r'\.+\s(/[^:\n]+)')
        error_pattern = re.compile(r'error:.*undefined reference to [`\']([^`\']+)[`\']')
        
        for line in log_content.splitlines():
            include_match = include_pattern.match(line)
            if include_match:
                included_file = Path(include_match.group(1))
                if current_file:
                    self.include_graph[current_file].add(included_file)
                    self.reverse_graph[included_file].add(current_file)
            elif 'In file included from' in line:
                current_file = Path(line.split(':')[0].split('from ')[-1].strip())
            elif 'error:' in line or 'warning:' in line:
                error_match = error_pattern.search(line)
                if error_match and current_file:
                    symbol = error_match.group(1)
                    self.undefined_symbols[current_file].add(symbol)

    def scan_header_content(self, file_path: Path) -> Set[str]:
        """Scansiona il contenuto di un header file per trovare definizioni."""
        definitions = set()
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                macro_pattern = re.compile(r'#\s*define\s+(\w+)')
                function_pattern = re.compile(r'\w+\s+(\w+)\s*\([^)]*\)\s*{?')
                type_pattern = re.compile(r'typedef\s+[^;]+\s+(\w+)\s*;')
                
                definitions.update(macro_pattern.findall(content))
                definitions.update(function_pattern.findall(content))
                definitions.update(type_pattern.findall(content))
        except Exception as e:
            print(f"Errore nella lettura del file {file_path}: {e}")
        return definitions

    def find_circular_dependencies(self) -> List[List[Path]]:
        """Trova le dipendenze circolari usando l'algoritmo di Tarjan."""
        # Creiamo una copia statica dei nodi all'inizio
        nodes = list(self.include_graph.keys())
        index_counter = [0]
        index = {}
        lowlink = {}
        on_stack = set()
        stack = []
        cycles = []

        def strongconnect(node: Path):
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack.add(node)

            # Creiamo una copia statica dei successori
            successors = list(self.include_graph[node])
            for successor in successors:
                if successor not in index:
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif successor in on_stack:
                    lowlink[node] = min(lowlink[node], index[successor])

            if lowlink[node] == index[node]:
                cycle = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    cycle.append(w)
                    if w == node:
                        break
                if len(cycle) > 1:
                    cycles.append(cycle)

        for node in nodes:  # Usiamo la lista statica invece del dizionario
            if node not in index:
                strongconnect(node)

        return cycles

    def analyze_and_print(self, base_path: Path = None):
        """Analizza e stampa un report completo."""
        print("\n=== Report Analisi Header ===")
        
        # Analisi dipendenze circolari
        try:
            cycles = self.find_circular_dependencies()
            if cycles:
                print("\nDipendenze Circolari Trovate:")
                for cycle in cycles:
                    print(" -> ".join(str(f) for f in cycle))
            else:
                print("\nNessuna dipendenza circolare trovata.")
        except Exception as e:
            print(f"\nErrore durante l'analisi delle dipendenze circolari: {e}")
        
        # Analisi simboli non definiti
        if self.undefined_symbols:
            print("\nSimboli Non Definiti:")
            for file, symbols in self.undefined_symbols.items():
                print(f"\nFile: {file}")
                for symbol in symbols:
                    print(f"  - {symbol}")
                    if base_path:
                        found_in = []
                        # Creiamo una copia statica dei file da analizzare
                        headers_to_check = list(self.include_graph.keys())
                        for header in headers_to_check:
                            full_path = base_path / header
                            if full_path.exists() and symbol in self.scan_header_content(full_path):
                                found_in.append(header)
                        if found_in:
                            print(f"    Potenzialmente definito in: {', '.join(str(f) for f in found_in)}")
        
        # Statistiche generali
        print("\nStatistiche:")
        print(f"Totale file analizzati: {len(self.include_graph)}")
        print(f"Totale inclusioni: {sum(len(deps) for deps in self.include_graph.values())}")
        print(f"Totale simboli non definiti: {sum(len(syms) for syms in self.undefined_symbols.values())}")

def analyze_build_log(log_path: str, project_base_path: str = None):
    """Funzione principale per l'analisi."""
    try:
        analyzer = HeaderAnalyzer()
        
        with open(log_path, 'r') as f:
            log_content = f.read()
        
        analyzer.parse_build_log(log_content)
        
        if project_base_path:
            base_path = Path(project_base_path)
            analyzer.analyze_and_print(base_path)
        else:
            analyzer.analyze_and_print()
        
        return analyzer
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    log_path = '../hello-idf/build_output.txt'
    project_base_path = '../hello-idf/'

    if len(sys.argv) > 2:
        log_path = sys.argv[1]
        project_base_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    analyze_build_log(log_path, project_base_path)
