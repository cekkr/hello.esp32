#wasm-objdump -h fibonacciPrint.wasm    # Mostra l'header e le sezioni
#wasm-objdump -x fibonacciPrint.wasm    # Dump dettagliato di tutte le sezioni

wasm2wat justLoop.wasm > wats/justLoop.wat
wasm2wat justLoop.64.wasm > wats/justLoop.64.wat