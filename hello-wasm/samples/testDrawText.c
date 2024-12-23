#include "../bindings/esp_wasm.h"

void start() {
    lcd_draw_text(30, 30, 12, "Hello WASM!");
}