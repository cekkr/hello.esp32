import os
import subprocess
import json
import re
import time
import logging
from pathlib import Path
import google.generativeai as genai

import os
import subprocess
import json
import re
import time
import logging
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass
import google.generativeai as genai

@dataclass
class SourceDefinition:
    name: str
    type: str
    line: int
    content: str
    file: Path

@dataclass
class SourceFile:
    path: Path
    definitions: List[SourceDefinition]
    includes: List[Path]
    raw_content: Optional[str] = None

class BuildAssistant:
    def __init__(self, esp_idf_path: str, gemini_api_key: str):
        # Setup logging
        self.logger = logging.getLogger('BuildAssistant')
        self.logger.setLevel(logging.DEBUG)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Init paths and API
        self.esp_idf_path = Path(esp_idf_path)
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Source analysis
        self.source_files: Dict[Path, SourceFile] = {}
        self.definitions_map: Dict[str, List[SourceDefinition]] = {}
        
        # Error patterns
        self.error_patterns = {
            'compilation': r'error: (.*)',
            'linking': r'undefined reference to `(.*)`',
            'cmake': r'CMake Error at (.*)',
            'fatal error': r'fatal error: (.*)',
            'undefined reference': r'undefined reference to `(.*)`',
            'failed': r'(?:make|ninja): \*\*\* (.*?) Error \d+'
        }
        
        # Code patterns
        self.code_patterns = {
            'function': r'(?:static\s+)?(?:void|int|char|float|double|bool|size_t|uint\w+_t|int\w+_t|\w+_t|\w+)\s+(\w+)\s*\([^)]*\)\s*{',
            'struct': r'struct\s+(\w+)\s*{',
            'typedef': r'typedef\s+(?:struct\s+)?(?:enum\s+)?(?:\w+\s+)?(\w+);',
            'define': r'#define\s+(\w+)',
            'variable': r'(?:static\s+)?(?:const\s+)?(?:volatile\s+)?(?:\w+(?:\s*\*)?)\s+(\w+)\s*(?:=|;)',
        }
        
        self._scan_source_files()
    
    def _scan_source_files(self):
        """Scansiona i file sorgente del progetto e analizza il loro contenuto."""
        self.logger.info("Scansione dei file sorgente...")
        
        extensions = {'.c', '.cpp', '.h', '.hpp'}
        for ext in extensions:
            for file_path in self.esp_idf_path.rglob(f'*{ext}'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    definitions = []
                    includes = []
                    
                    # Analizza include
                    for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
                        inc_path = match.group(1)
                        full_path = self.esp_idf_path / inc_path
                        if full_path.exists():
                            includes.append(full_path)
                    
                    # Analizza definizioni
                    for pattern_type, pattern in self.code_patterns.items():
                        for match in re.finditer(pattern, content):
                            name = match.group(1)
                            line = content[:match.start()].count('\n') + 1
                            def_content = content[match.start():match.end()]
                            
                            definition = SourceDefinition(
                                name=name,
                                type=pattern_type,
                                line=line,
                                content=def_content,
                                file=file_path
                            )
                            definitions.append(definition)
                            
                            if name not in self.definitions_map:
                                self.definitions_map[name] = []
                            self.definitions_map[name].append(definition)
                    
                    self.source_files[file_path] = SourceFile(
                        path=file_path,
                        definitions=definitions,
                        includes=includes,
                        raw_content=content
                    )
                    
                except Exception as e:
                    self.logger.error(f"Errore analizzando {file_path}: {e}")

    def get_context_for_error(self, error_info: Dict) -> Dict:
        """Trova informazioni di contesto relative all'errore."""
        context = {"relevant_definitions": [], "related_files": [], "includes": []}
        
        try:
            # Cerca definizioni correlate
            for error in error_info['errors']:
                message = error['message']
                
                # Estrai possibili identificatori dall'errore
                identifiers = re.findall(r'\b\w+\b', message)
                
                for identifier in identifiers:
                    if identifier in self.definitions_map:
                        for definition in self.definitions_map[identifier]:
                            context['relevant_definitions'].append({
                                'name': definition.name,
                                'type': definition.type,
                                'file': str(definition.file.relative_to(self.esp_idf_path)),
                                'line': definition.line,
                                'content': definition.content
                            })
                            
                            # Aggiungi file correlati
                            source_file = self.source_files[definition.file]
                            context['related_files'].append(str(definition.file.relative_to(self.esp_idf_path)))
                            context['includes'].extend([
                                str(inc.relative_to(self.esp_idf_path)) 
                                for inc in source_file.includes
                            ])
            
            # Rimuovi duplicati
            context['related_files'] = list(set(context['related_files']))
            context['includes'] = list(set(context['includes']))
            
        except Exception as e:
            self.logger.error(f"Errore nell'analisi del contesto: {e}")
        
        return context

    def get_solution(self, errors):
        """Ottiene una soluzione da Gemini con contesto arricchito."""
        if not errors:
            self.logger.warning("Nessun errore da analizzare")
            return None
            
        self.logger.info("Richiesta soluzione a Gemini")
        
        # Ottieni contesto aggiuntivo
        context = self.get_context_for_error({'errors': errors})
        
        prompt = f"""
        Analizza i seguenti errori di compilazione ESP-IDF e fornisci una soluzione dettagliata in formato JSON.
        
        Errori:
        {json.dumps(errors, indent=2)}
        
        Contesto del codice:
        {json.dumps(context, indent=2)}
        
        Rispondi SOLO con un JSON valido nel seguente formato:
        {{
            "analisi": "breve descrizione del problema",
            "causa": "causa probabile dell'errore",
            "contesto": "analisi del contesto fornito",
            "soluzione": [
                "passo 1",
                ...
            ],
            "suggerimenti": [
                "suggerimento 1",
                ...
            ],
            "richiesta_dettagli": [
                "informazioni riguardo alla struttura X",
                ...
            ]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            self.logger.debug(f"Risposta ricevuta: {response.text}")
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                self.logger.error("Impossibile parsare la risposta come JSON")
                return {"error": "Formato risposta non valido", "raw": response.text}
                
        except Exception as e:
            self.logger.error(f"Errore durante la richiesta a Gemini: {e}")
            return {"error": str(e)}
    
    def execute_build(self, build_script: str):
        """Esegue lo script di build"""
        self.logger.info(f"Esecuzione build script: {build_script}")
        try:
            result = subprocess.run(
                build_script,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.esp_idf_path
            )
            return result.stdout + result.stderr, result.returncode == 0
        except Exception as e:
            self.logger.error(f"Errore durante la build: {e}")
            return str(e), False
    
    def parse_errors(self, output: str):
        """Analizza l'output per trovare errori"""
        self.logger.info("Analisi degli errori")
        errors = []
        
        for line in output.split('\n'):
            for error_type, pattern in self.error_patterns.items():
                if match := re.search(pattern, line):
                    errors.append({
                        'type': error_type,
                        'message': match.group(1),
                        'context': line.strip()
                    })
                    self.logger.debug(f"Trovato errore: {error_type} - {match.group(1)}")
        
        return errors

    def get_solution(self, errors):
        """Ottiene una soluzione da Gemini"""
        if not errors:
            self.logger.warning("Nessun errore da analizzare")
            return None
            
        self.logger.info("Richiesta soluzione a Gemini")
        
        prompt = f"""
        Analizza i seguenti errori di compilazione ESP-IDF e fornisci una soluzione dettagliata in formato JSON:
        
        {json.dumps(errors, indent=2)}
        
        Rispondi SOLO con un JSON valido nel seguente formato:
        {{
            "analisi": "breve descrizione del problema",
            "causa": "causa probabile dell'errore",
            "soluzione": [
                "passo 1",
                ...
            ],
            "suggerimenti": [
                "suggerimento 1",
                ...
            ],
            "richiesta_dettagli":[
                "informazioni riguardo alla struttura X",
                ...
            ]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            self.logger.debug(f"Risposta ricevuta: {response.text}")
            
            # Prova a parsare la risposta come JSON
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                self.logger.error("Impossibile parsare la risposta come JSON")
                return {"error": "Formato risposta non valido", "raw": response.text}
                
        except Exception as e:
            self.logger.error(f"Errore durante la richiesta a Gemini: {e}")
            return {"error": str(e)}

    def run(self, build_script: str):
        """Esegue l'intero processo"""
        self.logger.info("Avvio analisi build")
        
        # Esegui build
        output, success = self.execute_build(build_script)
        
        if success:
            print("Build completata con successo!")
            return
        
        # Trova errori
        errors = self.parse_errors(output)
        if not errors:
            print("Build fallita ma nessun errore riconosciuto")
            return
            
        # Ottieni e mostra soluzione
        solution = self.get_solution(errors)
        if solution:
            print("\nAnalisi dell'errore:")
            print(json.dumps(solution, indent=2, ensure_ascii=False))


def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

# Esempio di utilizzo
def main():
    # Specifica il percorso del file geminiConfig.env
    config_file = 'geminiConfig.env'

    # Carica la chiave GEMINI_KEY dal file
    gemini_key = load_gemini_key(config_file)

    assistant = BuildAssistant(
        esp_idf_path="../hello-idf",
        gemini_api_key=gemini_key
    )
    
    assistant.run("./build.sh")

if __name__ == "__main__":
    main()