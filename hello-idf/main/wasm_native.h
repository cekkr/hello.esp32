// esp_wasm_bindings_impl.h
#ifndef ESP_WASM_BINDINGS_IMPL_H
#define ESP_WASM_BINDINGS_IMPL_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

// Implementazione della funzione printf per WASM
void wasm_esp_printf(const char* format, int32_t* args, int32_t arg_count) {
    // Buffer per costruire il messaggio formattato
    char message[256];
    char* current = message;
    const char* format_ptr = format;
    int arg_index = 0;

    while (*format_ptr && (current - message) < sizeof(message) - 1) {
        if (*format_ptr != '%') {
            *current++ = *format_ptr++;
            continue;
        }

        format_ptr++; // Skip '%'
        
        // Gestione dei format specifiers
        if (*format_ptr == 'd' && arg_index < arg_count) {
            int len = snprintf(current, sizeof(message) - (current - message), "%ld", args[arg_index++]);
            if (len > 0) {
                current += len;
            }
            format_ptr++;
        } 
        else if (*format_ptr == 's') {
            // Non supportiamo attualmente stringhe come varargs
            *current++ = '?';
            format_ptr++;
            arg_index++;
        }
        else {
            // Per qualsiasi altro formato, copiamo semplicemente %x
            *current++ = '%';
            *current++ = *format_ptr++;
        }
    }

    *current = '\0';
    ESP_LOGI("WASM", "%s", message);
}

#endif // ESP_WASM_BINDINGS_IMPL_H