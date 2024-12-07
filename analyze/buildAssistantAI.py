import os
import subprocess
import json
import re
import time
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from pathlib import Path
import logging
from google.api_core import retry

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
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimo 1 secondo tra le richieste
        
        # Regex comuni per il parsing degli errori
        self.error_patterns = {
            'compilation': r'error: (.*)',
            'linking': r'undefined reference to `(.*)`',
            'cmake': r'CMake Error at (.*)',
        }
        
    def _setup_logging(self) -> logging.Logger:
        """Configura il logging system con output verboso."""
        logger = logging.getLogger('ESPBuildAssistant')
        logger.setLevel(logging.DEBUG)  # Impostato a DEBUG per massima verbosità
        
        # Handler per console con formattazione dettagliata
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Handler per file di log
        file_handler = logging.FileHandler('esp_build_assistant.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger

    def _rate_limit_wait(self):
        """Implementa rate limiting per le richieste API."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            self.logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    async def analyze_build_output(self, build_output: str) -> Dict:
        """
        Analizza l'output della build per identificare errori.
        
        Args:
            build_output: Output grezzo della build
            
        Returns:
            Dict con analisi strutturata degli errori
        """
        self.logger.info("Iniziando analisi dell'output della build")
        self.logger.debug(f"Output completo della build:\n{build_output}")
        
        errors = []
        for line in build_output.split('\n'):
            for error_type, pattern in self.error_patterns.items():
                if match := re.search(pattern, line):
                    error = {
                        'type': error_type,
                        'message': match.group(1),
                        'context': line
                    }
                    self.logger.debug(f"Trovato errore: {error}")
                    errors.append(error)
        
        result = {'errors': errors}
        self.logger.info(f"Analisi completata. Trovati {len(errors)} errori")
        return result

    async def get_ai_assistance(self, error_info: Dict) -> Dict:
        """
        Ottiene assistenza da Gemini per risolvere gli errori.
        Implementa rate limiting e logging verboso.
        
        Args:
            error_info: Informazioni strutturate sull'errore
            
        Returns:
            Risposta strutturata da Gemini
        """
        self.logger.info("Preparazione richiesta a Gemini")
        prompt = self._build_prompt(error_info)
        self.logger.debug(f"Prompt generato:\n{prompt}")
        
        # Applica rate limiting
        self._rate_limit_wait()
        
        try:
            self.logger.info("Invio richiesta a Gemini")
            response = await self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 1024
                }
            )
            
            self.logger.debug(f"Risposta ricevuta da Gemini:\n{response.text}")
            
            try:
                parsed_response = json.loads(response.text)
                self.logger.info("Risposta JSON parsata con successo")
                self.logger.debug(f"Risposta parsata:\n{json.dumps(parsed_response, indent=2)}")
                return parsed_response
            except json.JSONDecodeError as e:
                self.logger.error(f"Errore nel parsing della risposta JSON: {e}")
                return {
                    "error": "Formato risposta non valido",
                    "raw_response": response.text
                }
                
        except Exception as e:
            self.logger.error(f"Errore nella richiesta a Gemini: {e}")
            raise

    def _build_prompt(self, error_info: Dict) -> str:
        """
        Costruisce il prompt per Gemini con istruzioni dettagliate.
        """
        prompt = f"""
        Analizza il seguente errore di compilazione ESP-IDF e fornisci una soluzione dettagliata in formato JSON.
        
        Errore: {json.dumps(error_info, indent=2)}
        
        Rispondi con un JSON che include:
        {{
            "problema": "descrizione dettagliata del problema riscontrato",
            "causa_probabile": "analisi approfondita della causa",
            "soluzione": {{
                "passi": [
                    "lista ordinata di passi da seguire",
                    "con spiegazioni dettagliate"
                ],
                "comandi": [
                    "eventuali comandi da eseguire"
                ]
            }},
            "codice_esempio": "esempio di codice corretto se applicabile",
            "riferimenti": [
                "link alla documentazione",
                "riferimenti utili"
            ]
        }}
        """
        return prompt

    async def execute_build(self, build_script: str) -> Tuple[str, bool]:
        """
        Esegue lo script di build e cattura l'output.
        
        Args:
            build_script: Percorso allo script di build
            
        Returns:
            Tuple con (output, success_status)
        """
        self.logger.info(f"Avvio build con script: {build_script}")
        
        try:
            self.logger.debug(f"Esecuzione comando in directory: {self.esp_idf_path}")
            result = subprocess.run(
                build_script,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.esp_idf_path
            )
            
            self.logger.debug(f"Output build:\n{result.stdout}")
            if result.stderr:
                self.logger.debug(f"Stderr build:\n{result.stderr}")
            
            success = result.returncode == 0
            self.logger.info(f"Build completata {'con successo' if success else 'con errori'}")
            
            return result.stdout + result.stderr, success
            
        except Exception as e:
            self.logger.error(f"Errore nell'esecuzione della build: {e}")
            return str(e), False

    async def run(self, build_script: str):
        """
        Esegue l'intero processo di build e analisi in modo controllato.
        
        Args:
            build_script: Script di build da eseguire
        """
        self.logger.info("Avvio processo di assistenza build")
        
        # Esegui build
        output, success = await self.execute_build(build_script)
        
        if success:
            self.logger.info("Build completata con successo!")
            return
            
        # Analizza errori
        error_analysis = await self.analyze_build_output(output)
        
        if not error_analysis['errors']:
            self.logger.warning("Build fallita ma nessun errore riconosciuto nel pattern")
            return
            
        # Ottieni assistenza
        self.logger.info("Richiesta assistenza per la risoluzione")
        assistance = await self.get_ai_assistance(error_analysis)
        
        # Stampa risultati
        print("\nAnalisi dell'errore:")
        print(json.dumps(assistance, indent=2, ensure_ascii=False))


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