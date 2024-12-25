#include "../bindings/esp_wasm.h"

void start() {
    esp_printf("Write something: \n");
    char* res = esp_read_serial();
    esp_printf("You wrote: %s\n", res);    
}