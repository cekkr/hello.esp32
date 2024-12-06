from dataclasses import dataclass
from typing import Dict, Set, List, Optional, Tuple
import re
import os
from pathlib import Path

@dataclass
class StructInfo:
    defined_in: Optional[str]        # File dove è definita completamente
    declared_in: Set[str]           # File dove è forward-declared
    dependencies: Set[str]          # Altre struct da cui dipende
    definition_line: Optional[int]   # Linea dove è definita

@dataclass
class IncludeState:
    current_stack: List[str]        # Stack corrente di inclusioni
    processed_guards: Set[str]      # Include guards già processati
    struct_info: Dict[str, StructInfo]  # Info su tutte le struct trovate

class IncludeStackAnalyzer:
    def __init__(self):
        self.include_states: Dict[str, IncludeState] = {}  # Stato per ogni file processato
        self.file_contents: Dict[str, str] = {}
        self.base_path = ""

    def parse_build_log(self, content: str) -> List[Tuple[str, str, int, List[str]]]:
        """
        Analizza il log di build per trovare errori e loro contesto
        Restituisce: [(file_con_errore, struct_name, line_num, include_stack)]
        """
        errors = []
        current_stack = []
        
        for line in content.splitlines():
            # Traccia lo stack delle inclusioni
            if line.startswith('.'):
                depth = line.count('.')
                filename = line.strip('. ')
                
                # Aggiorna lo stack corrente
                while len(current_stack) > depth:
                    current_stack.pop()
                if depth == len(current_stack):
                    if current_stack:
                        current_stack.pop()
                current_stack.append(filename)
                
                # Analizza il file per le definizioni di struct
                self.analyze_file(filename)
            
            # Trova errori di struct non definita
            elif 'error: invalid use of undefined type' in line:
                match = re.search(r'([^:]+):(\d+):\d+: error: invalid use of undefined type.*struct (\w+)', line)
                if match:
                    file, line_num, struct_name = match.groups()
                    errors.append((file, struct_name, int(line_num), current_stack.copy()))
        
        return errors

    def analyze_file(self, filepath: str) -> None:
        """Analizza un file per trovare definizioni e dipendenze di struct"""
        if filepath in self.include_states:
            return
            
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                self.file_contents[filepath] = content
            
            state = IncludeState(
                current_stack=[],
                processed_guards=set(),
                struct_info={}
            )
            
            # Trova ifdef guards
            guard_match = re.search(r'#ifndef\s+(\w+)', content)
            if guard_match:
                state.processed_guards.add(guard_match.group(1))
            
            # Trova definizioni complete di struct
            struct_defs = re.finditer(r'struct\s+(\w+)\s*{([^}]+)}', content)
            for match in struct_defs:
                struct_name = match.group(1)
                definition = match.group(2)
                
                # Trova dipendenze (altre struct usate nella definizione)
                deps = set(re.findall(r'struct\s+(\w+)', definition))
                
                state.struct_info[struct_name] = StructInfo(
                    defined_in=filepath,
                    declared_in=set(),
                    dependencies=deps,
                    definition_line=content[:match.start()].count('\n') + 1
                )
            
            # Trova forward declarations
            struct_decls = re.finditer(r'struct\s+(\w+)\s*;', content)
            for match in struct_decls:
                struct_name = match.group(1)
                if struct_name not in state.struct_info:
                    state.struct_info[struct_name] = StructInfo(
                        defined_in=None,
                        declared_in={filepath},
                        dependencies=set(),
                        definition_line=None
                    )
                else:
                    state.struct_info[struct_name].declared_in.add(filepath)
            
            self.include_states[filepath] = state
            
        except (FileNotFoundError, IOError) as e:
            print(f"Warning: Could not analyze {filepath}: {e}")

    def find_struct_definition_chain(self, struct_name: str, include_stack: List[str]) -> Dict:
        """
        Analizza perché una struct non è disponibile dove serve
        """
        result = {
            "struct_name": struct_name,
            "definition": None,
            "forward_declarations": set(),
            "circular_dependencies": [],
            "blocking_includes": [],
            "suggestions": []
        }
        
        # Cerca la definizione della struct
        for file, state in self.include_states.items():
            if struct_name in state.struct_info:
                info = state.struct_info[struct_name]
                if info.defined_in:
                    result["definition"] = (info.defined_in, info.definition_line)
                result["forward_declarations"].update(info.declared_in)
                
                # Verifica se la definizione è bloccata da inclusioni circolari
                if info.defined_in in include_stack:
                    def_index = include_stack.index(info.defined_in)
                    cycle = include_stack[def_index:]
                    result["circular_dependencies"].append(cycle)
                    
                    # Aggiungi suggerimenti specifici
                    result["suggestions"].extend([
                        f"1. La struct '{struct_name}' è definita in {os.path.basename(info.defined_in)} "
                        f"ma questo file è già in fase di inclusione:",
                        "   " + " -> ".join(os.path.basename(f) for f in cycle),
                        "",
                        "Possibili soluzioni:",
                        f"a) Aggiungi 'struct {struct_name};' in " + 
                        os.path.basename(include_stack[-1]),
                        f"b) Sposta la definizione di {struct_name} in un nuovo file header " +
                        "che non dipende da nessuno dei file nel ciclo",
                        "c) Riorganizza le dipendenze per rompere il ciclo"
                    ])
        
        if not result["definition"] and not result["forward_declarations"]:
            result["suggestions"].append(
                f"La struct '{struct_name}' non è definita in nessun file analizzato"
            )
        
        return result

    def print_analysis(self, error_file: str, struct_name: str, line_num: int, include_stack: List[str]):
        """Stampa l'analisi dettagliata per un errore"""
        print(f"\nAnalyzing error: undefined struct '{struct_name}' in {os.path.basename(error_file)}:{line_num}")
        
        print("\nInclude stack at error point:")
        for i, file in enumerate(include_stack):
            prefix = "-> " if i == len(include_stack) - 1 else "   "
            print(f"{prefix}{os.path.basename(file)}")
        
        analysis = self.find_struct_definition_chain(struct_name, include_stack)
        
        if analysis["definition"]:
            file, line = analysis["definition"]
            print(f"\nStruct is defined in: {os.path.basename(file)}:{line}")
        
        if analysis["circular_dependencies"]:
            print("\nCircular include dependencies detected:")
            for cycle in analysis["circular_dependencies"]:
                print("  " + " -> ".join(os.path.basename(f) for f in cycle))
        
        if analysis["suggestions"]:
            print("\nAnalysis and suggestions:")
            for suggestion in analysis["suggestions"]:
                print(suggestion)

def main():
    analyzer = IncludeStackAnalyzer()
    
    try:
        with open('../hello-idf/build_output.txt', 'r') as f:
            content = f.read()
            
        errors = analyzer.parse_build_log(content)
        
        for error_file, struct_name, line_num, include_stack in errors:
            analyzer.print_analysis(error_file, struct_name, line_num, include_stack)
            
    except FileNotFoundError:
        print("build_output.txt not found. Please redirect build output to this file.")

if __name__ == "__main__":
    main()