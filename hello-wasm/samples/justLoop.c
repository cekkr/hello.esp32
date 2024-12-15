#include <stdint.h>
#include <emscripten.h>

#include "../bindings/bindings.c"

EMSCRIPTEN_KEEPALIVE
void print_num(int i){
    esp_printf("Num: %d\n", i);
}

EMSCRIPTEN_KEEPALIVE
void start() {
    for(int i = 0; i <100; i++){
        print_num(i);
    }
}