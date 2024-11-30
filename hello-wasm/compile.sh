# npm install -g assemblyscript # install assemblyscript

asc samples/fibonacci.ts -o output/fibonacci.wasm --optimize
# xxd -i output/fibonacci.wasm > output/fibonacci_wasm.h # to convert to c array

