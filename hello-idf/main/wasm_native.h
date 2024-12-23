#ifndef HELLOESP_NATIVE_H
#define HELLOESP_NATIVE_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

#include "m3_env.h"
#include "m3_segmented_memory.h"

///
///
///

const char* ERROR_MSG_NULLS = "wasm_esp_printf: runtime or _mem is null";
const char* ERROR_MSG_FAILED = "wasm_esp_printf: failed";

const bool HELLO_DEBUG_wasm_esp_printf = false;
M3Result wasm_esp_printf(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if(HELLO_DEBUG_wasm_esp_printf){
        ESP_LOGI("WASM3", "Entering wasm_esp_printf with params:");
        ESP_LOGI("WASM3", "  runtime: %p", runtime);
        ESP_LOGI("WASM3", "  ctx: %p", ctx);
        ESP_LOGI("WASM3", "  _sp: %p", _sp);
        ESP_LOGI("WASM3", "  _mem: %p", _mem);
    }

    bool runtime_null = (runtime == NULL);
    bool mem_null = (_mem == NULL);
    
    if(HELLO_DEBUG_wasm_esp_printf){
        ESP_LOGI("WASM3", "runtime_null: %d", runtime_null);
        ESP_LOGI("WASM3", "mem_null: %d", mem_null);
    }

    if (runtime_null || mem_null) {
        ESP_LOGW("WASM3", "wasm_esp_printf blocked: runtime=%p, _sp=%p, mem=%p", runtime, _sp, _mem);
        LOG_FLUSH;
        //return ERROR_MSG_NULLS;
    }

    uint64_t* stack = m3ApiOffsetToPtr(_sp);
    _sp++;

    char formatted_output[512];  // Increased buffer for safety
    
    // Recupera e valida il puntatore al formato
    const char* format = m3ApiOffsetToPtr(stack[0]);    
    if (!format) {
        ESP_LOGE("WASM3", "esp_printf: Invalid format string pointer");
        return ERROR_MSG_FAILED;
    }

    if(HELLO_DEBUG_wasm_esp_printf) ESP_LOGE("WASM3", "wasm_esp_printf: format(%p): %s", format, format);

    void* args_ptr = m3ApiOffsetToPtr(stack[1]);
    if (!args_ptr) {
        ESP_LOGE("WASM3", "esp_printf: Invalid format string pointer");
        return ERROR_MSG_FAILED;
    }

    // Array per memorizzare gli argomenti processati
    union {
        int32_t i;
        uint32_t u;
        float f;
        const char* s;
        void* p;
    } args[16];  // Supporta fino a 16 argomenti
    int arg_count = 0;

    // Analizza la stringa di formato per determinare il numero di argomenti
    const char* fmt_ptr = format;
    while (*fmt_ptr) {
        if (*fmt_ptr == '%') {
            fmt_ptr++;
            if (*fmt_ptr != '%') {  // Ignora %%
                if (arg_count >= 16) {
                    ESP_LOGE("WASM3", "esp_printf: Too many arguments");
                    return ERROR_MSG_FAILED;
                }

                // Processa l'argomento basandosi sul tipo
                void* stack_ptr = m3ApiOffsetToPtr(args_ptr);
                switch (*fmt_ptr) {
                    case 'd': case 'i': case 'u': case 'x': case 'X':
                        args[arg_count].i = m3ApiReadMem32(stack_ptr);
                        break;
                    case 'f':
                        // Gestione float con controllo del tipo
                        args[arg_count].f = *(float*)stack_ptr;
                        break;
                    case 's': {
                        // Gestione stringhe con validazione del puntatore
                        args[arg_count].s = m3ApiOffsetToPtr(stack_ptr);
                        if (!args[arg_count].s) {
                            ESP_LOGE("WASM3", "esp_printf: Invalid string pointer");
                            return ERROR_MSG_FAILED;
                        }
                        break;
                    }
                    case 'p': {
                        // Gestione puntatori
                        args[arg_count].p = m3ApiOffsetToPtr(stack_ptr);
                        break;
                    }                    
                }
                args_ptr += sizeof(uint64_t*);
                arg_count++;
            }
        }
        fmt_ptr++;
    }

    // Debug logging
    if(HELLO_DEBUG_wasm_esp_printf) ESP_LOGD("WASM3", "esp_printf: Format: %s, ArgCount: %d", format, arg_count);

    // Formatta l'output usando vsnprintf
    int result = snprintf(formatted_output, sizeof(formatted_output),
                         format,
                         args[0].i, args[1].i, args[2].i, args[3].i,
                         args[4].i, args[5].i, args[6].i, args[7].i,
                         args[8].i, args[9].i, args[10].i, args[11].i,
                         args[12].i, args[13].i, args[14].i, args[15].i);

    if (result >= 0 && result < sizeof(formatted_output)) {
        ESP_LOGI("WASM3", "%s", formatted_output);
    } else {
        ESP_LOGE("WASM3", "esp_printf: Formatting error");
        return ERROR_MSG_FAILED;
    }

    return NULL;
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