import re
from collections import defaultdict
import sys

def count_dots(line):
    """Conta il numero di punti all'inizio della riga per determinare il livello di indentazione"""
    return len(re.match(r'\.+', line).group(0)) if line.startswith('.') else 0

def parse_cmake_log(log_content):
    """
    Analizza il contenuto del log cmake per estrarre le dipendenze ricorsive.
    """
    # Dizionario per memorizzare le dipendenze per ogni file
    dependencies = defaultdict(set)
    
    # Stack per tenere traccia del percorso di inclusione corrente
    inclusion_stack = []
    
    # Converte il log in liste di righe e rimuove le righe vuote
    lines = [line.strip() for line in log_content.split('\n') if line.strip()]
    
    current_level = 0
    for line in lines:
        # Salta le righe che non contengono informazioni sui file
        if line.startswith('In file included from'):
            continue
            
        # Se la riga inizia con punti, è una dipendenza
        if line.startswith('.'):
            level = count_dots(line)
            file_path = line[level:].strip()
            
            # Aggiorna lo stack delle inclusioni in base al livello
            while len(inclusion_stack) > level:
                inclusion_stack.pop()
                
            if inclusion_stack:
                # Aggiungi la dipendenza al file corrente
                dependencies[inclusion_stack[-1]].add(file_path)
                
            inclusion_stack.append(file_path)
            current_level = level

    return dependencies

def detect_circular_dependencies(dependencies):
    """
    Identifica le dipendenze circolari nel grafo delle dipendenze.
    """
    def find_cycle(node, visited, path):
        if node in path:
            cycle_start = path.index(node)
            return path[cycle_start:]
        if node in visited:
            return []
            
        visited.add(node)
        path.append(node)
        
        for neighbor in dependencies.get(node, []):
            cycle = find_cycle(neighbor, visited, path.copy())
            if cycle:
                return cycle
                
        return []

    circular_deps = []
    visited = set()
    
    for node in dependencies:
        if node not in visited:
            cycle = find_cycle(node, visited, [])
            if cycle:
                circular_deps.append(cycle)
                
    return circular_deps

def print_dependencies(dependencies):
    """
    Stampa le dipendenze in modo strutturato e leggibile.
    """
    print("\nAnalisi delle dipendenze:")
    for source_file, deps in sorted(dependencies.items()):
        if deps:  # Stampa solo i file che hanno dipendenze
            print(f"\nFile: {source_file}")
            print("Dipendenze:")
            for dep in sorted(deps):
                print(f"  → {dep}")

    # Trova e stampa le dipendenze circolari
    circular = detect_circular_dependencies(dependencies)
    if circular:
        print("\nDipendenze circolari trovate:")
        for cycle in circular:
            print(" → ".join(cycle))
    else:
        print("\nNessuna dipendenza circolare trovata.")

def main():
    """
    Funzione principale che legge il file di log e analizza le dipendenze.
    """
    if len(sys.argv) != 2:
        print("Uso: python script.py <cmake_log_file>")
        sys.exit(1)
        
    try:
        with open(sys.argv[1], 'r') as f:
            log_content = f.read()
    except FileNotFoundError:
        print(f"Errore: File {sys.argv[1]} non trovato")
        sys.exit(1)
    except Exception as e:
        print(f"Errore durante la lettura del file: {e}")
        sys.exit(1)
        
    dependencies = parse_cmake_log(log_content)
    print_dependencies(dependencies)

if __name__ == "__main__":
    main()

# python3 cmakeLogs.py ../hello-idf/build_output.txt