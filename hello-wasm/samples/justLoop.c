#include <stdint.h>
#include <emscripten.h>

#include "../bindings/esp_wasm.h"

void print_num(int i){
    esp_printf("Num: %d\n", i);
}

void start() {
    for(int i = 0; i <100; i++){
        print_num(i);
    }
}