#wasm-objdump -h fibonacciPrint.wasm    # Mostra l'header e le sezioni
#wasm-objdump -x fibonacciPrint.wasm    # Dump dettagliato di tutte le sezioni

wasm2wat fibonacciPrint.wasm > wats/fibonacciPrint.wat
wasm2wat fibonacciPrint_keepAlive.wasm > wats/fibonacciPrint_keepAlive.wat
wasm2wat justLoop.wasm > wats/justLoop.wat