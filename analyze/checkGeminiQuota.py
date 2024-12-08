import google.generativeai as genai
import json
from datetime import datetime
import logging

# Configura il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_gemini_quota(api_key):
    """
    Controlla la quota disponibile per le API di Google Gemini.
    
    Args:
        api_key (str): La chiave API di Google Cloud/Gemini
        
    Returns:
        dict: Informazioni sulla quota e stato della richiesta
    """
    try:
        # Configura l'accesso API
        genai.configure(api_key=api_key)
        
        # Inizializza il modello
        model = genai.GenerativeModel('gemini-pro')
        
        # Esegui una richiesta di prova
        response = model.generate_content(
            "test",
            generation_config={
                "max_output_tokens": 1
            }
        )
        
        # Verifica se la richiesta ha avuto successo
        if hasattr(response, 'candidates'):
            status = "success"
        else:
            status = "incomplete_response"
            
        # Raccogli le informazioni disponibili
        quota_info = {
            'status': status,
            'response_type': str(type(response)),
            'available_attributes': dir(response),
            'checked_at': datetime.now().isoformat(),
            'model': 'gemini-pro'
        }
        
        # Se disponibili, aggiungi ulteriori dettagli sulla risposta
        if hasattr(response, 'prompt_feedback'):
            quota_info['prompt_feedback'] = str(response.prompt_feedback)
            
        if hasattr(response, 'candidates'):
            quota_info['candidates_count'] = len(response.candidates)
        
        return quota_info
        
    except Exception as e:
        logger.error(f"Errore durante il controllo della quota: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'checked_at': datetime.now().isoformat()
        }


def load_gemini_key(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('GEMINI_KEY='):
                return line.split('=')[1].strip()
    return None

if __name__ == "__main__":
    # Inserisci qui la tua API key
    API_KEY =  load_gemini_key("geminiConfig.env")
    
    # Controlla la quota
    quota = check_gemini_quota(API_KEY)
    
    # Stampa i risultati
    print(json.dumps(quota, indent=2))