import re
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
import ast
import logging
from pathlib import Path

@dataclass
class MacroDefinition:
    name: str
    params: List[str]
    body: str
    original_text: str
    line_number: int

@dataclass
class MacroExpansion:
    macro_name: str
    args: List[str]
    context: str
    line_number: int

class WASM3MacroAnalyzer:
    def __init__(self):
        self.macro_definitions: Dict[str, MacroDefinition] = {}
        self.macro_expansions: List[MacroExpansion] = []
        self.return_patterns = {
            'nextOp': r'nextOp\s*\(\)',
            'outOfBounds': r'd_outOfBounds',
            'errorMissing': r'c_m3ErrorMissing',
        }
        self.control_flow_patterns = {
            'if': r'if\s*\([^{]*\)\s*{',
            'else': r'else\s*{',
            'for': r'for\s*\([^{]*\)\s*{',
            'while': r'while\s*\([^{]*\)\s*{',
        }
        
    def parse_macro_definitions(self, content: str) -> None:
        """Analizza e memorizza tutte le definizioni di macro."""
        # Pattern per identificare le definizioni di macro
        macro_def_pattern = r'#define\s+(\w+)\s*\(([\w\s,]*)\)\s*(\\\s*\n(?:.*\\\s*\n)*.*)'
        
        for match in re.finditer(macro_def_pattern, content, re.MULTILINE):
            name = match.group(1)
            params = [p.strip() for p in match.group(2).split(',') if p.strip()]
            body = match.group(3)
            
            self.macro_definitions[name] = MacroDefinition(
                name=name,
                params=params,
                body=body,
                original_text=match.group(0),
                line_number=content[:match.start()].count('\n') + 1
            )

    def analyze_control_flow(self, macro_body: str) -> List[dict]:
        """Analizza il flusso di controllo all'interno di una macro."""
        flow_points = []
        lines = macro_body.split('\n')
        current_depth = 0
        
        for i, line in enumerate(lines):
            # Analizza apertura/chiusura blocchi
            current_depth += line.count('{') - line.count('}')
            
            # Cerca pattern di controllo del flusso
            for pattern_name, pattern in self.control_flow_patterns.items():
                if re.search(pattern, line):
                    flow_points.append({
                        'type': pattern_name,
                        'line': i,
                        'depth': current_depth,
                        'needs_return': True
                    })
                    
            # Cerca return impliciti
            for ret_name, ret_pattern in self.return_patterns.items():
                if re.search(ret_pattern, line) and not re.search(r'return\s+', line):
                    flow_points.append({
                        'type': 'implicit_return',
                        'line': i,
                        'depth': current_depth,
                        'pattern': ret_name
                    })
                    
        return flow_points

    def add_returns(self, macro_body: str) -> str:
        """Aggiunge i return mancanti alla macro."""
        flow_points = self.analyze_control_flow(macro_body)
        lines = macro_body.split('\n')
        
        # Aggiungi return per ogni punto di flusso che ne necessita
        for point in reversed(flow_points):  # Procedi dal basso per non alterare i numeri di riga
            if point['type'] == 'implicit_return':
                line = lines[point['line']].rstrip('\\')
                if not line.strip().startswith('return'):
                    lines[point['line']] = f"return {line}"
                if point['line'] < len(lines) - 1:
                    lines[point['line']] += ' \\'
                    
        # Se non c'è un return esplicito alla fine, aggiungilo
        if not any('return' in line for line in lines):
            last_line = lines[-1].rstrip('\\')
            if 'nextOp()' in last_line and 'return' not in last_line:
                lines[-1] = f"return {last_line}"
            else:
                lines.append("    return nextOp();\\")
                
        return '\n'.join(lines)

    def process_file(self, input_path: str, output_path: str) -> None:
        """Processa il file completo."""
        try:
            with open(input_path, 'r') as f:
                content = f.read()
                
            # Prima analizza tutte le definizioni
            self.parse_macro_definitions(content)
            
            # Poi processa ogni macro
            for macro in self.macro_definitions.values():
                fixed_body = self.add_returns(macro.body)
                content = content.replace(macro.body, fixed_body)
                
            # Scrivi il risultato
            with open(output_path, 'w') as f:
                f.write(content)
                
            logging.info(f"File processato con successo: {output_path}")
                
        except Exception as e:
            logging.error(f"Errore durante il processing del file: {str(e)}")
            raise


if __name__ == "__main__":
    input_path = "../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/m3_exec.h"
    output_path = "m3_exec_transformed.h"
    
    logging.basicConfig(level=logging.INFO)
    analyzer = WASM3MacroAnalyzer()
    
    analyzer.process_file(input_path, output_path)