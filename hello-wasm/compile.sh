#/bin/bash

# npm install -g assemblyscript # install assemblyscript

asc samples/fibonacci.ts -o output/fibonacci.wasm --optimize
# xxd -i output/fibonacci.wasm > output/fibonacci_wasm.h # to convert to c array

#clang --target=wasm32 -nostdlib -Wl,--no-entry -Wl,--export-all -o output/fibonacciPrint.wasm samples/fibonacciPrint.c

#-s TOTAL_MEMORY=65536 -s TOTAL_STACK=16384

compile_wasm() {
    local script_name=$1
    
    # Verifica se il nome dello script è stato fornito
    if [ -z "$script_name" ]; then
        echo "Errore: Fornire il nome dello script da compilare"
        echo "Uso: compile_wasm nome_script"
        return 1
    fi
    
    # Verifica se il file sorgente esiste
    if [ ! -f "samples/${script_name}.c" ]; then
        echo "Errore: Il file samples/${script_name}.c non esiste"
        return 1
    fi
    
    # Crea la directory output se non esiste
    mkdir -p output
    
    # Imposta la memoria in base al nome dello script
    local memory_size="65536"
    local stack_size="16384"
    
    # Configura parametri specifici per script diversi
    case $script_name in
        "justLoop")
            stack_size="4096"
            ;;
    esac
    
    echo "Compilazione di ${script_name}..."
    
    emcc "samples/${script_name}.c" -o "output/${script_name}.wasm" \
        -s WASM=1 \
        -s STANDALONE_WASM=0 \
        -s IMPORTED_MEMORY=1 \
        -s STACK_SIZE=${stack_size} \
        -s ALLOW_MEMORY_GROWTH=1 \
        -s EXPORTED_FUNCTIONS='["_start"]' \
        --no-entry \
        -O1 \
        -fno-inline 
        #-s INITIAL_MEMORY=${memory_size} \
        #-g 
        
    if [ $? -eq 0 ]; then
        echo "Compilazione completata con successo"
    else
        echo "Errore durante la compilazione"
    fi
}

# Esempio di utilizzo:
compile_wasm fibonacciPrint
compile_wasm fibonacciPrint_keepAlive
compile_wasm justLoop