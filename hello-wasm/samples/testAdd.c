#include "../bindings/esp_wasm.h"

void start() {
    int res = esp_add(3, 2);
    esp_printf("esp_add 3 + 2 = %d\n", res);
}