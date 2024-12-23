#ifndef ESP32_WASM_BINDINGS_H
#define ESP32_WASM_BINDINGS_H

#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>

// Auto-generated ESP32 WASM bindings

/*
// Controls an LED connected to a GPIO pin
void esp_led_write(int32_t pin, int32_t level);

// Reads an ADC channel
int32_t esp_adc_read(int32_t channel);

// Reads the internal temperature sensor
float esp_get_temperature();

// Performs a WiFi scan and returns number of networks found
int32_t esp_wifi_scan();
*/

// Printf-like function for ESP32
extern void esp_printf(const char* format, ...)  __attribute__((import_module("env"), import_name("esp_printf")));

extern void lcd_draw_text(int x, int y, int size, const char* text)  __attribute__((import_module("env"), import_name("lcd_draw_text")));

extern int esp_add(int a, int b)  __attribute__((import_module("env"), import_name("esp_add")));

#endif // ESP32_WASM_BINDINGS_H
