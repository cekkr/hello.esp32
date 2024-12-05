import os
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

class IncludeAnalyzer:
    def __init__(self):
        self.include_order: List[str] = []  # Mantiene l'ordine esatto delle inclusioni
        self.errors: List[Tuple[str, str, int]] = []
        self.base_path = ""
        
    def extract_base_path(self, file_path: str) -> str:
        """Estrae il path base dal primo file analizzato"""
        components = file_path.split('/components/')
        if len(components) > 1:
            return components[0] + '/components/'
        return ""

    def parse_build_output(self, output_text: str):
        """Parse the build output to extract include hierarchy and errors"""
        current_include_stack = []
        
        for line in output_text.splitlines():
            # Analizza le linee che mostrano l'inclusione dei file
            if line.startswith('.'):
                depth = line.count('.')
                filepath = line.strip('. ')
                
                # Imposta il base_path al primo file trovato
                if not self.base_path and filepath:
                    self.base_path = self.extract_base_path(filepath)
                
                # Gestisce lo stack delle inclusioni
                while len(current_include_stack) > depth:
                    current_include_stack.pop()
                    
                if len(current_include_stack) == depth:
                    if current_include_stack:
                        current_include_stack.pop()
                
                current_include_stack.append(filepath)
                if filepath not in self.include_order:
                    self.include_order.append(filepath)
            
            # Traccia gli errori
            if 'error: invalid use of undefined type' in line:
                match = re.search(r'([^:]+):(\d+):\d+: error: invalid use of undefined type.*struct (\w+)', line)
                if match:
                    file, line_num, struct_name = match.groups()
                    self.errors.append((file, struct_name, int(line_num)))

    def analyze_file_content(self, filepath: str) -> Tuple[List[str], List[str], List[str]]:
        """Analizza un singolo file per trovare include, forward declarations e definizioni"""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
        except (FileNotFoundError, IOError):
            return [], [], []

        includes = re.findall(r'#include [<"]([^>"]+)[>"]', content)
        forward_decls = re.findall(r'struct\s+(\w+);', content)
        struct_defs = re.findall(r'struct\s+(\w+)\s*{[^}]+}', content)
        
        return includes, forward_decls, struct_defs

    def find_file_in_includes(self, partial_path: str) -> Optional[str]:
        """Cerca un file nel base_path"""
        if self.base_path:
            full_path = os.path.join(self.base_path, partial_path)
            if os.path.exists(full_path):
                return full_path
        return None

    def print_analysis(self):
        """Stampa l'analisi dettagliata"""
        print("\n=== Include Order at Error Time ===")
        
        # Per ogni errore, mostra lo stato delle inclusioni a quel punto
        for error_file, struct_name, line_num in self.errors:
            print(f"\nAnalyzing error: undefined struct {struct_name} in {error_file}:{line_num}")
            print("\nInclude stack up to error:")
            
            # Trova l'indice del file con l'errore nella sequenza di include
            try:
                error_index = next(i for i, path in enumerate(self.include_order) 
                                 if error_file in path)
                
                # Mostra tutte le inclusioni fino al punto dell'errore
                for i, filepath in enumerate(self.include_order[:error_index + 1]):
                    depth = filepath.count('/')
                    print(f"{'  ' * depth}→ {os.path.basename(filepath)}")
                    
                    # Analizza il contenuto di ogni file
                    includes, forwards, structs = self.analyze_file_content(filepath)
                    
                    if forwards:
                        print(f"{'  ' * (depth+1)}Forward declarations: {', '.join(forwards)}")
                    if structs:
                        print(f"{'  ' * (depth+1)}Struct definitions: {', '.join(structs)}")
                    
                    # Se questo file contiene una dichiarazione o definizione della struct che causa l'errore
                    if struct_name in forwards:
                        print(f"{'  ' * (depth+1)}*** Forward declaration of {struct_name} found here")
                    if struct_name in structs:
                        print(f"{'  ' * (depth+1)}*** Full definition of {struct_name} found here")
                    
            except StopIteration:
                print(f"Could not find {error_file} in include sequence")

def main():
    analyzer = IncludeAnalyzer()
    
    try:
        with open('build_output.txt', 'r') as f:
            analyzer.parse_build_output(f.read())
    except FileNotFoundError:
        print("build_output.txt not found. Please redirect build output to this file.")
        return
    
    analyzer.print_analysis()

if __name__ == "__main__":
    main()