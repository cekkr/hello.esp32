if __name__ == '__main__':
    filename = 'sdkconfig'
    
    try:
        # Leggi tutto il contenuto
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Scrivi il contenuto filtrato
        with open(filename, 'w') as f:
            for line in lines:
                if not (line.startswith('# CONFIG_') and line.endswith('is not set\n')):
                    f.write(line)
        
        print("File sdkconfig pulito con successo")
    except FileNotFoundError:
        print(f"Errore: Il file {filename} non è stato trovato")
    except Exception as e:
        print(f"Si è verificato un errore: {str(e)}")