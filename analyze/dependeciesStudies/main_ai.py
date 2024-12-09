from readCLib import *

def main():
    project_paths = "../../hello-idf/components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3"

    if len(sys.argv) >= 2:
        project_paths = sys.argv[1:]
    
    project_paths = os.path.abspath(project_paths)
    
    try:
        analyzer = SourceAnalyzer(project_paths)
        print("Analisi del progetto in corso...")
        analyzer.analyze()
        
        printAndDive = False
        if printAndDive:
            analyzer.print_dependencies()
            analyzer.print_symbols()
            analyzer.find_cycles()
            analyzer.suggest_missing_includes()
            
            # Opzionale: analisi dettagliata di simboli specifici
            while True:
                symbol = input("\nInserisci il nome di un simbolo da analizzare (o premi Invio per terminare): ")
                if not symbol:
                    break
                analyzer.analyze_symbol(symbol)
        else:
            pass # analyze dependencies
    
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")
        raise

if __name__ == "__main__":
    main()