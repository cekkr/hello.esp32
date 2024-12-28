import re
import os

def modify_m3op_lines(file_path):
    try:
        # Legge il file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Counter per l'indice
        current_index = 0
        
        # Funzione per processare ogni match
        def replace_match(match):
            nonlocal current_index
            full_match = match.group(0)
            # Trova la posizione della prima virgola
            comma_pos = full_match.find(',')
            if comma_pos == -1:
                return full_match
                
            # Ricostruisce la stringa sostituendo il numero dopo la prima virgola
            start_part = full_match[:comma_pos+1]  # Include la virgola
            rest_part = full_match[comma_pos+1:]   # Parte dopo la virgola
            # Trova la prossima virgola o parentesi per determinare dove finisce il numero
            next_separator = rest_part.find(',')
            if next_separator == -1:
                next_separator = rest_part.find(')')
            if next_separator == -1:
                return full_match
                
            # Sostituisce il numero con l'indice corrente
            new_line = f"{start_part} {current_index}{rest_part[next_separator:]}"
            current_index += 1
            return new_line

        # Pattern regex che cattura l'intera linea M3OP
        pattern = r'(M3OP|M3OP_F)\s*(\([^()]*(?:\([^()]*\)[^()]*)*\))'
        
        # Effettua la sostituzione
        modified_content = re.sub(pattern, replace_match, content)
        
        # Crea il nome del nuovo file con .modified.c
        base_name, ext = os.path.splitext(file_path)
        output_path = f"{base_name}.modified.c"
        
        # Scrive il contenuto modificato nel nuovo file
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(modified_content)
        
        print(f"File modificato salvato come: {output_path}")
        
        # Stampa un confronto delle prime righe modificate per verifica
        print("\nPrime righe del file originale:")
        print(content.split('\n')[:10])
        print("\nPrime righe del file modificato:")
        print(modified_content.split('\n')[:10])
        
    except Exception as e:
        print(f"Si è verificato un errore: {str(e)}")


# Esempio di utilizzo
if __name__ == "__main__":
    file_path = "hello-idf/main/wasm3/source/m3_compile.c"  # Sostituire con il path del file
    modify_m3op_lines(file_path)