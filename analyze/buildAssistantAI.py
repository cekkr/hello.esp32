import os
import subprocess
import json
import re
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from pathlib import Path
import logging

class ESPBuildAssistant:
    def __init__(self, esp_idf_path: str, gemini_api_key: str):
        """
        Inizializza l'assistente di build ESP-IDF con integrazione Gemini.
        
        Args:
            esp_idf_path: Percorso alla directory ESP-IDF
            gemini_api_key: API key per Gemini
        """
        self.esp_idf_path = Path(esp_idf_path)
        self.logger = self._setup_logging()
        
        # Configurazione Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Regex comuni per il parsing degli errori
        self.error_patterns = {
            'compilation': r'error: (.*)',
            'linking': r'undefined reference to `(.*)`',
            'cmake': r'CMake Error at (.*)',
        }
        
    def _setup_logging(self) -> logging.Logger:
        """Configura il logging system."""
        logger = logging.getLogger('ESPBuildAssistant')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    async def analyze_build_output(self, build_output: str) -> Dict:
        """
        Analizza l'output della build per identificare errori.
        
        Args:
            build_output: Output grezzo della build
            
        Returns:
            Dict con analisi strutturata degli errori
        """
        errors = []
        for line in build_output.split('\n'):
            for error_type, pattern in self.error_patterns.items():
                if match := re.search(pattern, line):
                    errors.append({
                        'type': error_type,
                        'message': match.group(1),
                        'context': line
                    })
        
        return {'errors': errors}

    async def get_ai_assistance(self, error_info: Dict, detail_level: int = 1) -> Dict:
        """
        Ottiene assistenza da Gemini per risolvere gli errori.
        
        Args:
            error_info: Informazioni strutturate sull'errore
            detail_level: Livello di dettaglio richiesto (1-3)
            
        Returns:
            Risposta strutturata da Gemini
        """
        prompt = self._build_prompt(error_info, detail_level)
        
        response = await self.model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 1024
            }
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Impossibile parsare la risposta JSON da Gemini")
            return {"error": "Formato risposta non valido"}

    def _build_prompt(self, error_info: Dict, detail_level: int) -> str:
        """Costruisce il prompt per Gemini basato sul livello di dettaglio."""
        base_prompt = f"""
        Analizza il seguente errore di compilazione ESP-IDF e fornisci una soluzione strutturata in formato JSON.
        Livello di dettaglio richiesto: {detail_level} (1=base, 2=intermedio, 3=dettagliato)
        
        Errore: {json.dumps(error_info, indent=2)}
        
        Rispondi con un JSON che include:
        {{
            "problema": "descrizione concisa del problema",
            "causa_probabile": "spiegazione della causa",
            "soluzione": "steps per risolvere",
            "codice_esempio": "esempio di codice corretto se applicabile",
            "approfondimenti": "link e riferimenti per maggiori dettagli"
        }}
        """
        return base_prompt

    async def execute_build(self, build_script: str) -> Tuple[str, bool]:
        """
        Esegue lo script di build e cattura l'output.
        
        Args:
            build_script: Percorso allo script di build
            
        Returns:
            Tuple con (output, success_status)
        """
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
            self.logger.error(f"Errore nell'esecuzione della build: {e}")
            return str(e), False

    async def interactive_assistance(self, build_script: str):
        """
        Fornisce assistenza interattiva durante il processo di build.
        
        Args:
            build_script: Script di build da eseguire
        """
        self.logger.info("Avvio processo di build...")
        output, success = await self.execute_build(build_script)
        
        if success:
            self.logger.info("Build completata con successo!")
            return
            
        error_analysis = await self.analyze_build_output(output)
        detail_level = 1
        
        while True:
            assistance = await self.get_ai_assistance(error_analysis, detail_level)
            print("\nAnalisi dell'errore:")
            print(json.dumps(assistance, indent=2, ensure_ascii=False))
            
            user_input = input("\nVuoi maggiori dettagli? (s/n/q per uscire): ").lower()
            if user_input == 'q':
                break
            elif user_input == 's' and detail_level < 3:
                detail_level += 1
            elif user_input == 'n':
                break

def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

# Esempio di utilizzo
async def main():
    # Specifica il percorso del file geminiConfig.env
    config_file = 'geminiConfig.env'

    # Carica la chiave GEMINI_KEY dal file
    gemini_key = load_gemini_key(config_file)

    assistant = ESPBuildAssistant(
        esp_idf_path="../hello-idf",
        gemini_api_key=gemini_key
    )
    
    await assistant.interactive_assistance("./build.sh")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())