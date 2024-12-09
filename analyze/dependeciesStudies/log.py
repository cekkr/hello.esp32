import sys
import subprocess
import logging

# Configura il logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Crea un file handler per salvare i log
file_handler = logging.FileHandler('output.log')
file_handler.setLevel(logging.DEBUG)

logger.info(f"\n\n================================================\n\n New execution:\n\n")

# Crea uno stream handler per stampare i log sul terminale
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

# Imposta il formato dei log
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Aggiungi gli handler al logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Verifica se è stato fornito il nome del file Python come argomento
if len(sys.argv) < 2:
    print("Utilizzo: python script_runner.py <nome_file.py> [argomenti...]")
    sys.exit(1)

# Ottieni il nome del file Python e gli argomenti dalla riga di comando
python_file = sys.argv[1]
args = sys.argv[2:]

# Esegui il file Python con gli argomenti forniti
try:
    result = subprocess.run(['/Library/Frameworks/Python.framework/Versions/3.12/bin/python3', python_file] + args, capture_output=True, text=True)
    stdout = result.stdout
    stderr = result.stderr

    # Stampa l'output dello script eseguito sia sul terminale che nel file di log
    logger.info(f"Output dello script '{python_file}':")
    logger.info(stdout)

    # Stampa eventuali errori sia sul terminale che nel file di log
    if stderr:
        logger.error(f"Errori dello script '{python_file}':")
        logger.error(stderr)

except FileNotFoundError:
    logger.error(f"File '{python_file}' non trovato.")
    sys.exit(1)