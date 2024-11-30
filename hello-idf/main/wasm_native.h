// esp_wasm_bindings_impl.h
#ifndef ESP_WASM_BINDINGS_IMPL_H
#define ESP_WASM_BINDINGS_IMPL_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

// Implementazione della funzione printf per WASM
void wasm_esp_printf(const char* format, int32_t* args, int32_t arg_count) {
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
        
        // Gestione della larghezza del campo
        char width[10] = {0};
        int width_idx = 0;
        while (*format_ptr >= '0' && *format_ptr <= '9' && width_idx < 9) {
            width[width_idx++] = *format_ptr++;
        }
        
        // Gestione della precisione
        char precision[10] = {0};
        int precision_idx = 0;
        if (*format_ptr == '.') {
            format_ptr++;
            while (*format_ptr >= '0' && *format_ptr <= '9' && precision_idx < 9) {
                precision[precision_idx++] = *format_ptr++;
            }
        }

        if (arg_index >= arg_count) {
            *current++ = '?';
            format_ptr++;
            continue;
        }

        switch (*format_ptr) {
            case 'd':
            case 'i': {
                int len = snprintf(current, sizeof(message) - (current - message), 
                                 width[0] ? "%*ld" : "%ld", 
                                 width[0] ? atoi(width) : 0, 
                                 args[arg_index++]);
                if (len > 0) current += len;
                break;
            }
            case 'f': {
                float val = *((float*)&args[arg_index++]);
                int len = snprintf(current, sizeof(message) - (current - message),
                                 precision[0] ? "%.*f" : "%f",
                                 precision[0] ? atoi(precision) : 6,
                                 (double)val);  // Cast esplicito a double
                break;
            }
            case 'x': {
                int len = snprintf(current, sizeof(message) - (current - message),
                                 "%lx",
                                 (unsigned long)args[arg_index++]);
                if (len > 0) current += len;
                break;
            }
            case 'X': {
                int len = snprintf(current, sizeof(message) - (current - message),
                                 "%lX",
                                 (unsigned long)args[arg_index++]);
                if (len > 0) current += len;
                break;
            }
            case '%':
                *current++ = '%';
                arg_index--;  // Non consuma un argomento
                break;
            default:
                *current++ = '?';
                break;
        }
        format_ptr++;
    }

    *current = '\0';
    ESP_LOGI(TAG, "%s", message);
}

#endif // ESP_WASM_BINDINGS_IMPL_H