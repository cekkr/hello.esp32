#ifndef HELLOESP_NATIVE_H
#define HELLOESP_NATIVE_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

#include "m3_env.h"

static const bool HELLO_DEBUG_WASM_NATIVE = true;

// Implementazione della funzione printf per WASM
void wasm_esp_printf__(uint8_t* format, int32_t* args, int32_t arg_count) { // currently not used
    ESP_LOGD(TAG, "Called wasm_esp_printf");

    char message[256];
    char* current = message;
    const uint8_t* format_ptr = format;
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

///
/// Natives
///

m3ApiRawFunction(wasm_esp_printf__2) {
    ESP_LOGD(TAG, "wasm_esp_printf__2 called");

    m3ApiReturnType(int32_t)
    
    // Ottieni il puntatore al formato dalla memoria WASM
    m3ApiGetArgMem(const char*, format);

    ESP_LOGD(TAG, "wasm_esp_printf__2: format: %s", format);
    
    // Buffer per il risultato formattato
    char formatted_output[256];
    int result = 0;
    
    // Ottieni gli argomenti variabili basati sul formato
    const char* ptr = format;
    int arg_count = 0;
    
    // Conta i parametri nel formato
    while (*ptr) {
        if (*ptr == '%') {
            ptr++;
            if (*ptr != '%') {  // Ignora %%
                arg_count++;
            }
        }
        ptr++;
    }
    
    // Gestisci fino a 8 argomenti
    int32_t args[8] = {0};
    for (int i = 0; i < arg_count && i < 8; i++) {
        m3ApiGetArg(int32_t, value);
        args[i] = value;
    }
    
    // Formatta l'output in base al numero di argomenti
    switch (arg_count) {
        case 0:
            result = snprintf(formatted_output, sizeof(formatted_output), format);
            break;
        case 1:
            result = snprintf(formatted_output, sizeof(formatted_output), format, args[0]);
            break;
        case 2:
            result = snprintf(formatted_output, sizeof(formatted_output), format, args[0], args[1]);
            break;
        case 3:
            result = snprintf(formatted_output, sizeof(formatted_output), format, args[0], args[1], args[2]);
            break;
        case 4:
            result = snprintf(formatted_output, sizeof(formatted_output), format, args[0], args[1], args[2], args[3]);
            break;
        default:
            ESP_LOGW(TAG, "Too many format arguments (max 4 supported)");
            result = -1;
    }
    
    if (result >= 0) {
        ESP_LOGI(TAG, "%s", formatted_output);
    }
    
    m3ApiReturn(result);
}


///
///
///

M3Result wasm_esp_printf(IM3Runtime runtime, IM3ImportContext _ctx, uint64_t* _sp, void* _mem) {
    ESP_LOGD(TAG, "wasm_esp_printf called");

    int32_t* args = (int32_t*)_sp;
    char formatted_output[256];
    int result = 0;
    
    // Ottieni il puntatore al formato dalla memoria lineare
    const char* format = m3ApiOffsetToPtr(args[0]);
    if (!format) {
        return m3Err_malformedUtf8;
    }
    
    // Verifica la validità del puntatore al formato
    if (!runtime) {
        return m3Err_malformedUtf8;
    }
    
    // Conta i parametri nel formato
    const char* ptr = format;
    int arg_count = 0;
    while (*ptr) {
        if (*ptr == '%') {
            ptr++;
            if (*ptr != '%') {  // Ignora %%
                arg_count++;
            }
        }
        ptr++;
    }
    
    // Array per memorizzare gli argomenti
    int32_t values[8] = {0};
    
    // Leggi gli argomenti dallo stack
    for (int i = 0; i < arg_count && i < 8; i++) {
        values[i] = m3ApiReadMem32(_sp + i + 1);
    }
    
    // Formatta in base al numero di argomenti
    switch (arg_count) {
        case 0:
            result = snprintf(formatted_output, sizeof(formatted_output), format);
            break;
        case 1:
            result = snprintf(formatted_output, sizeof(formatted_output), format, values[0]);
            break;
        case 2:
            result = snprintf(formatted_output, sizeof(formatted_output), format, values[0], values[1]);
            break;
        case 3:
            result = snprintf(formatted_output, sizeof(formatted_output), format, values[0], values[1], values[2]);
            break;
        case 4:
            result = snprintf(formatted_output, sizeof(formatted_output), format, values[0], values[1], values[2], values[3]);
            break;
        default:
            ESP_LOGW("WASM3", "Too many format arguments (max 4 supported)");
            return m3Err_malformedUtf8;
    }
    
    if (result < 0 || result >= sizeof(formatted_output)) {
        return m3Err_malformedUtf8;
    }
    
    // Stampa l'output formattato
    ESP_LOGI("WASM3", "%s", formatted_output);
    
    return m3Err_none;
}

// Definizione della lookup table entry
const WasmFunctionEntry functionTable[] = {
    { 
        .name = (const char*)"esp_printf",           // Nome della funzione in WASM
        .func = wasm_esp_printf,    // Puntatore alla funzione
        .signature = (const char*)"v(ii)"        // Signature: void (raw_ptr, int32)
    },
    // Altre funzioni possono essere aggiunte qui
};

M3Result registerNativeWASMFunctions(IM3Module module){
    M3Result result = RegisterWasmFunctions(module, functionTable, sizeof(functionTable)/sizeof(functionTable[0]));
    if (result) {
        ESP_LOGE(TAG, "Failed to register functions: %s", result);
    }

    return result;
}

#endif 