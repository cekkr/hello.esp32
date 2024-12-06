import os
from pathlib import Path

def check_directory(directory_path: str):
    """Verifica dettagliatamente una directory e mostra il suo contenuto"""
    # Converti in percorso assoluto
    abs_path = os.path.abspath(directory_path)
    print(f"\nVerifica directory: {abs_path}")
    
    # Informazioni sul percorso corrente di esecuzione
    print(f"Directory corrente di esecuzione: {os.getcwd()}")
    
    if not os.path.exists(abs_path):
        print(f"ERRORE: Il percorso {abs_path} non esiste!")
        return
    
    print("\nContenuto directory:")
    for root, dirs, files in os.walk(abs_path):
        level = root.replace(abs_path, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = '  ' * (level + 1)
        
        # Prima stampa le directory
        for d in dirs:
            print(f"{sub_indent}[DIR] {d}")
        
        # Poi stampa i file
        for f in files:
            full_path = os.path.join(root, f)
            size = os.path.getsize(full_path)
            print(f"{sub_indent}[FILE] {f} ({size} bytes)")
            
            # Se è un file .h, mostra le prime righe
            if f.endswith('.h'):
                try:
                    with open(full_path, 'r', encoding='utf-8') as file:
                        first_lines = file.readlines()[:3]
                        print(f"{sub_indent}  Prime righe:")
                        for line in first_lines:
                            print(f"{sub_indent}    {line.rstrip()}")
                except Exception as e:
                    print(f"{sub_indent}  Errore lettura: {e}")

def main():
    # Directory da verificare
    base_dirs = [
        '../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi',
        '../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3'
    ]
    
    print("=== Informazioni di sistema ===")
    print(f"Directory di lavoro corrente: {os.getcwd()}")
    
    for dir_path in base_dirs:
        # Prova sia il percorso relativo che quello assoluto
        abs_path = os.path.abspath(dir_path)
        print(f"\n=== Verifica percorso: {dir_path} ===")
        print(f"Percorso assoluto: {abs_path}")
        
        # Verifica esistenza
        if os.path.exists(abs_path):
            print("Il percorso esiste")
            check_directory(abs_path)
        else:
            print("Il percorso NON esiste!")
            
            # Prova a risolvere il percorso in modo diverso
            alternative_path = Path(dir_path).resolve()
            print(f"\nProvando percorso alternativo: {alternative_path}")
            if os.path.exists(alternative_path):
                print("Il percorso alternativo esiste")
                check_directory(str(alternative_path))
            else:
                print("Anche il percorso alternativo NON esiste!")

if __name__ == "__main__":
    main()