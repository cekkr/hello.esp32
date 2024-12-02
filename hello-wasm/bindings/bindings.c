#ifndef HELLOESP_WASM_BINDINGS_H
#define HELLOESP_WASM_BINDINGS_H

// Dichiarazione della funzione esterna
void esp_printf(const char* format, ...) __attribute__((import_module("env"), import_name("esp_printf")));

#endif