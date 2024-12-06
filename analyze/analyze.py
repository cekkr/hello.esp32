import os
import re
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class IncludeInfo:
    includes: List[str]
    struct_decls: Set[str]
    struct_defs: Set[str]
    ifdef_guard: Optional[str]

class CircularDependencyAnalyzer:
    def __init__(self):
        self.file_info: Dict[str, IncludeInfo] = {}
        self.include_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self.base_path = ""
        self.errors: List[Tuple[str, str, int]] = []
        self.known_paths: Dict[str, str] = {}  # Mappa da filename a full path

    def extract_base_paths(self, output_text: str) -> List[str]:
        """Estrae tutti i possibili base paths dal log di build"""
        paths = set()
        for line in output_text.splitlines():
            if line.startswith('.'):
                filepath = line.strip('. ')
                dir_path = os.path.dirname(filepath)
                paths.add(dir_path)
                # Aggiunge il mapping filename -> full path
                self.known_paths[os.path.basename(filepath)] = filepath
        return list(paths)

    def find_file(self, filename: str) -> Optional[str]:
        """Cerca un file usando varie strategie"""
        # 1. Se abbiamo già il path completo nei known_paths
        if filename in self.known_paths:
            return self.known_paths[filename]

        # 2. Se è un path relativo e abbiamo il base_path
        if self.base_path:
            full_path = os.path.join(self.base_path, filename)
            if os.path.exists(full_path):
                return full_path

        # 3. Cerca in tutti i base paths conosciuti
        for base_path in self.base_paths:
            full_path = os.path.join(base_path, filename)
            if os.path.exists(full_path):
                return full_path

            # Cerca anche nelle sottodirectory
            for root, _, files in os.walk(base_path):
                if filename in files:
                    return os.path.join(root, filename)

        return None

    def analyze_file(self, filepath: str, processed: Set[str] = None) -> IncludeInfo:
        """Analizza un file e i suoi include ricorsivamente"""
        if processed is None:
            processed = set()

        # Normalizza il filepath e cerca il file se necessario
        if not os.path.isabs(filepath):
            found_path = self.find_file(filepath)
            if found_path:
                filepath = found_path
            else:
                print(f"Warning: Could not find {filepath} in any known location")
                return IncludeInfo([], set(), set(), None)

        if filepath in self.file_info:
            return self.file_info[filepath]

        if filepath in processed:
            return IncludeInfo([], set(), set(), None)

        processed.add(filepath)

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            ifdef_match = re.search(r'#ifndef\s+(\w+)', content)
            ifdef_guard = ifdef_match.group(1) if ifdef_match else None

            includes = []
            for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
                included_file = match.group(1)
                includes.append(included_file)
                
                # Cerca il path completo del file incluso
                included_path = self.find_file(included_file)
                if included_path:
                    self.include_graph[filepath].add(included_path)
                    self.reverse_graph[included_path].add(filepath)
                    # Analizza ricorsivamente il file incluso
                    self.analyze_file(included_path, processed)

            struct_decls = set(re.findall(r'struct\s+(\w+)\s*;', content))
            struct_defs = set(re.findall(r'struct\s+(\w+)\s*{[^}]+}', content))

            info = IncludeInfo(includes, struct_decls, struct_defs, ifdef_guard)
            self.file_info[filepath] = info

            return info

        except (FileNotFoundError, IOError) as e:
            print(f"Warning: Could not analyze {filepath}: {e}")
            return IncludeInfo([], set(), set(), None)

    def parse_build_output(self, output_text: str):
        """Inizializza l'analizzatore con il build output"""
        # Prima estrai tutti i possibili base paths
        self.base_paths = self.extract_base_paths(output_text)
        
        # Poi estrai gli errori
        for line in output_text.splitlines():
            if 'error: invalid use of undefined type' in line:
                match = re.search(r'([^:]+):(\d+):\d+: error: invalid use of undefined type.*struct (\w+)', line)
                if match:
                    file, line_num, struct_name = match.groups()
                    # Usa find_file per ottenere il path completo
                    full_path = self.find_file(os.path.basename(file))
                    if full_path:
                        self.errors.append((full_path, struct_name, int(line_num)))
                    else:
                        self.errors.append((file, struct_name, int(line_num)))

    def print_analysis(self):
        """Stampa l'analisi completa"""
        for error_file, struct_name, line_num in self.errors:
            print(f"\nAnalyzing error: undefined struct '{struct_name}' in {os.path.basename(error_file)}:{line_num}")
            
            # Analizza disponibilità della struct
            availability = self.analyze_struct_availability(struct_name, error_file)
            
            if availability.get("status") == "not_found":
                print(f"\nStruct '{struct_name}' non è definita in nessun file analizzato")
                continue
                
            if availability.get("status") == "circular_dependency":
                print("\nRilevata dipendenza circolare:")
                for cycle in availability["cycles"]:
                    print("\nCiclo di inclusione:")
                    for i, file in enumerate(cycle):
                        info = self.file_info.get(file)
                        guard = f" (guard: {info.ifdef_guard})" if info and info.ifdef_guard else ""
                        print(f"{'  ' * i}→ {os.path.basename(file)}{guard}")
                    
                self.suggest_solutions(availability["cycles"], struct_name)

    def analyze_struct_availability(self, struct_name: str, file_needing: str) -> Dict[str, str]:
        """Analizza dove una struct è definita e perché non è disponibile dove serve"""
        result = {
            "status": None,
            "definitions": [],
            "declarations": [],
            "include_paths": [],
            "blocked_by": []
        }
        
        # Trova tutti i file che definiscono o dichiarano la struct
        for file, info in self.file_info.items():
            if struct_name in info.struct_defs:
                result["definitions"].append(file)
            elif struct_name in info.struct_decls:
                result["declarations"].append(file)
                
        if not result["definitions"] and not result["declarations"]:
            result["status"] = "not_found"
            return result
                
        # Per ogni definizione trovata
        for def_file in result["definitions"]:
            # Cerca un percorso di inclusione
            path = self.find_include_path(file_needing, def_file)
            if path:
                result["include_paths"].append(path)
                
                # Verifica se ci sono cicli che coinvolgono questi file
                cycles = self.find_cycles()
                blocking_cycles = []
                for cycle in cycles:
                    if def_file in cycle or file_needing in cycle:
                        blocking_cycles.append(cycle)
                        
                if blocking_cycles:
                    result["status"] = "circular_dependency"
                    result["blocked_by"].extend(blocking_cycles)
            else:
                result["status"] = "no_include_path"
                
        # Se abbiamo solo forward declarations
        if not result["definitions"] and result["declarations"]:
            result["status"] = "only_forward_declared"
            
        return result
    
    def find_include_path(self, from_file: str, to_file: str) -> Optional[List[str]]:
        """
        Trova un percorso di inclusione tra due file, considerando include diretti e indiretti.
        
        Args:
            from_file: File che ha bisogno della definizione
            to_file: File che contiene la definizione
        
        Returns:
            Optional[List[str]]: Lista di file che formano il percorso di inclusione,
                                None se non esiste un percorso
        """
        # Già nello stesso file
        if from_file == to_file:
            return [from_file]
            
        visited = set()
        path_stack = []
        
        def dfs(current_file: str) -> bool:
            # Se siamo arrivati al file target
            if current_file == to_file:
                return True
                
            # Aggiungi il file corrente al path e ai visitati
            visited.add(current_file)
            path_stack.append(current_file)
            
            # Controlla tutti i file inclusi direttamente
            for included_file in self.include_graph.get(current_file, set()):
                # Se non è già stato visitato
                if included_file not in visited:
                    # Se questo path porta al target
                    if dfs(included_file):
                        return True
                        
            # Se arriviamo qui, questo path non porta al target
            path_stack.pop()
            return False

        # Prova a trovare un percorso
        if dfs(from_file):
            # Aggiungi il file target al percorso finale
            path_stack.append(to_file)
            
            # Per ogni file nel percorso, verifica se gli include guards bloccano l'inclusione
            for i in range(len(path_stack)-1):
                current = path_stack[i]
                info = self.file_info.get(current)
                if info and info.ifdef_guard:
                    # Verifica se qualche file precedente nel path ha lo stesso guard
                    for prev in path_stack[:i]:
                        prev_info = self.file_info.get(prev)
                        if prev_info and prev_info.ifdef_guard == info.ifdef_guard:
                            print(f"Warning: Include guard {info.ifdef_guard} might block inclusion path at {os.path.basename(current)}")
            
            return path_stack
        
        return None
    
    def find_cycles(self) -> List[List[str]]:
        """
        Trova tutti i cicli di dipendenza nel grafo delle inclusioni.
        Usa l'algoritmo di Tarjan per trovare le componenti fortemente connesse (SCC).
        
        Returns:
            List[List[str]]: Lista di cicli trovati, dove ogni ciclo è una lista di file
        """
        def tarjan_scc(node: str, stack: List[str], indices: Dict[str, int], lowlinks: Dict[str, int], 
                    on_stack: Set[str], index: List[int], sccs: List[List[str]]):
            # Inizializza i valori per il nodo corrente
            indices[node] = index[0]
            lowlinks[node] = index[0]
            index[0] += 1
            stack.append(node)
            on_stack.add(node)
            
            # Visita tutti i vicini
            for neighbor in self.include_graph.get(node, set()):
                if neighbor not in indices:
                    # Vicino non ancora visitato
                    tarjan_scc(neighbor, stack, indices, lowlinks, on_stack, index, sccs)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    # Il vicino è sullo stack -> abbiamo trovato un back-edge
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])
            
            # Se questo è un nodo radice di una SCC
            if lowlinks[node] == indices[node]:
                # Estrai la SCC dallo stack
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                
                # Aggiungi la SCC solo se è un ciclo (più di un nodo o self-loop)
                if len(scc) > 1 or (len(scc) == 1 and scc[0] in self.include_graph.get(scc[0], set())):
                    sccs.append(scc)
        
        # Inizializza le strutture dati per Tarjan
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Set[str] = set()
        stack: List[str] = []
        index = [0]  # Lista di un elemento per permettere la modifica nell'inner function
        sccs: List[List[str]] = []
        
        # Esegui Tarjan su ogni nodo non ancora visitato
        for node in self.include_graph:
            if node not in indices:
                tarjan_scc(node, stack, indices, lowlinks, on_stack, index, sccs)
        
        # Post-processing dei cicli trovati
        processed_cycles = []
        for scc in sccs:
            # Verifica che i nodi della SCC formino effettivamente un ciclo
            if self.verify_cycle(scc):
                # Ordina il ciclo per renderlo più leggibile
                ordered_cycle = self.order_cycle(scc)
                if ordered_cycle:
                    processed_cycles.append(ordered_cycle)
        
        return processed_cycles

    def verify_cycle(self, components: List[str]) -> bool:
        """
        Verifica che una componente fortemente connessa formi effettivamente un ciclo di inclusioni.
        
        Args:
            components: Lista di file che potrebbero formare un ciclo
            
        Returns:
            bool: True se i componenti formano un ciclo valido
        """
        if len(components) < 2:
            return False
            
        # Verifica che ogni componente sia effettivamente collegato al successivo
        for i in range(len(components)):
            current = components[i]
            next_component = components[(i + 1) % len(components)]
            
            # Verifica se esiste un collegamento diretto
            if next_component not in self.include_graph.get(current, set()):
                return False
        
        return True

    def order_cycle(self, cycle: List[str]) -> Optional[List[str]]:
        """
        Ordina i componenti di un ciclo in modo che formino una sequenza valida di inclusioni.
        
        Args:
            cycle: Lista di file che formano un ciclo
            
        Returns:
            Optional[List[str]]: Ciclo ordinato o None se non è possibile ordinare
        """
        if not cycle:
            return None
            
        ordered = [cycle[0]]
        remaining = set(cycle[1:])
        
        while remaining:
            current = ordered[-1]
            # Cerca il prossimo file che è incluso direttamente
            next_file = None
            for candidate in remaining:
                if candidate in self.include_graph.get(current, set()):
                    next_file = candidate
                    break
            
            if next_file is None:
                # Non è stato possibile trovare una sequenza valida
                return None
                
            ordered.append(next_file)
            remaining.remove(next_file)
        
        # Verifica che il ciclo si chiuda
        if ordered[0] not in self.include_graph.get(ordered[-1], set()):
            return None
            
        return ordered

def main():
    analyzer = CircularDependencyAnalyzer()
    
    try:
        # Leggi il build output
        with open('../hello-idf/build_output.txt', 'r') as f:
            content = f.read()
            analyzer.parse_build_output(content)
        
        # Analizza i file coinvolti
        for error_file, _, _ in analyzer.errors:
            analyzer.analyze_file(error_file)
        
        analyzer.print_analysis()
        
    except FileNotFoundError:
        print("build_output.txt not found. Please redirect build output to this file.")
        return

if __name__ == "__main__":
    main()