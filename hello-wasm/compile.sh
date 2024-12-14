#/bin/bash

# npm install -g assemblyscript # install assemblyscript

asc samples/fibonacci.ts -o output/fibonacci.wasm --optimize
# xxd -i output/fibonacci.wasm > output/fibonacci_wasm.h # to convert to c array

#clang --target=wasm32 -nostdlib -Wl,--no-entry -Wl,--export-all -o output/fibonacciPrint.wasm samples/fibonacciPrint.c
emcc samples/fibonacciPrint.c -o output/fibonacciPrint.wasm \
    -s WASM=1 \
    -s STANDALONE_WASM=0 \
    -s IMPORTED_MEMORY=1 \
    -s INITIAL_MEMORY=65536 \
    -s STACK_SIZE=1024 \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s EXPORTED_FUNCTIONS='["_start"]' \
    -O3 \
    --no-entry 

    #todo: study ALLOW_MEMORY_GROWTH
    #-s STANDALONE_WASM=1 \
    #-s EXPORTED_FUNCTIONS='["_main", "_print_fibonacci"]' \
    #-s ERROR_ON_UNDEFINED_SYMBOLS=1 \
    #-s TOTAL_MEMORY=65536 \
    #-s TOTAL_STACK=2048 \
    #-s ALLOW_MEMORY_GROWTH=0 \
    #-s EXPORTED_RUNTIME_METHODS=[] \
    #-s DECLARE_ASM_MODULE_EXPORTS=0 \
    #--no-entry
    ##-s IMPORTED_FUNCTIONS='["_esp_printf"]' \ # it doesn't even exist as argument