import os
import subprocess
import json
import re
import time
import logging
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass
import requests

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
        self.gemini_api_key = gemini_api_key
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        
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

    def _call_gemini_api(self, prompt: str) -> dict:
        """Makes a direct API call to Gemini."""
        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        url = f"{self.gemini_url}?key={self.gemini_api_key}"
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            if 'candidates' in result and result['candidates']:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                raise ValueError("No valid response from Gemini API")
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return {"error": str(e)}
    
    def _scan_source_files(self):
        """Scans project source files and analyzes their content."""
        self.logger.info("Scanning source files...")
        
        extensions = {'.c', '.cpp', '.h', '.hpp'}
        for ext in extensions:
            for file_path in self.esp_idf_path.rglob(f'*{ext}'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    definitions = []
                    includes = []
                    
                    # Analyze includes
                    for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
                        inc_path = match.group(1)
                        full_path = self.esp_idf_path / inc_path
                        if full_path.exists():
                            includes.append(full_path)
                    
                    # Analyze definitions
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
                    self.logger.error(f"Error analyzing {file_path}: {e}")

    def get_context_for_error(self, error_info: Dict) -> Dict:
        """Finds context information related to the error."""
        context = {"relevant_definitions": [], "related_files": [], "includes": []}
        
        try:
            # Look for related definitions
            for error in error_info['errors']:
                message = error['message']
                
                # Extract possible identifiers from error
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
                            
                            # Add related files
                            source_file = self.source_files[definition.file]
                            context['related_files'].append(str(definition.file.relative_to(self.esp_idf_path)))
                            context['includes'].extend([
                                str(inc.relative_to(self.esp_idf_path)) 
                                for inc in source_file.includes
                            ])
            
            # Remove duplicates
            context['related_files'] = list(set(context['related_files']))
            context['includes'] = list(set(context['includes']))
            
        except Exception as e:
            self.logger.error(f"Error in context analysis: {e}")
        
        return context

    def get_solution(self, errors):
        """Gets a solution from Gemini with enriched context."""
        if not errors:
            self.logger.warning("No errors to analyze")
            return None
            
        self.logger.info("Requesting solution from Gemini")
        
        # Get additional context
        context = self.get_context_for_error({'errors': errors})
        
        prompt = f"""
        Analyze the following ESP-IDF compilation errors and provide a detailed solution in JSON format.
        
        Errors:
        {json.dumps(errors, indent=2)}
        
        Code context:
        {json.dumps(context, indent=2)}
        
        Respond ONLY with a valid JSON in the following format:
        {{
            "analysis": "brief problem description",
            "cause": "probable error cause",
            "context": "provided context analysis",
            "solution": [
                "step 1",
                ...
            ],
            "suggestions": [
                "suggestion 1",
                ...
            ],
            "request_details": [
                "information about structure X",
                ...
            ]
        }}
        """
        
        try:
            response = self._call_gemini_api(prompt)
            self.logger.debug(f"Response received: {response}")
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                self.logger.error("Unable to parse response as JSON")
                return {"error": "Invalid response format", "raw": response}
                
        except Exception as e:
            self.logger.error(f"Error during Gemini request: {e}")
            return {"error": str(e)}
    
    def execute_build(self, build_script: str):
        """Executes the build script"""
        self.logger.info(f"Executing build script: {build_script}")
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
            self.logger.error(f"Error during build: {e}")
            return str(e), False
    
    def parse_errors(self, output: str):
        """Analyzes output for errors"""
        self.logger.info("Analyzing errors")
        errors = []
        
        for line in output.split('\n'):
            for error_type, pattern in self.error_patterns.items():
                if match := re.search(pattern, line):
                    errors.append({
                        'type': error_type,
                        'message': match.group(1),
                        'context': line.strip()
                    })
                    self.logger.debug(f"Found error: {error_type} - {match.group(1)}")
        
        return errors

    def run(self, build_script: str):
        """Executes the entire process"""
        self.logger.info("Starting build analysis")
        
        # Execute build
        output, success = self.execute_build(build_script)
        
        if success:
            print("Build completed successfully!")
            return
        
        # Find errors
        errors = self.parse_errors(output)
        if not errors:
            print("Build failed but no recognized errors")
            return
            
        # Get and show solution
        solution = self.get_solution(errors)
        if solution:
            print("\nError analysis:")
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