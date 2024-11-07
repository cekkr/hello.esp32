# npm install -g assemblyscript # install assemblyscript

asc fibonacci.ts -b fibonacci.wasm --optimize

# xxd -i fibonacci.wasm > fibonacci_wasm.h # to convert to c array