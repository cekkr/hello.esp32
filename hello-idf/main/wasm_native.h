#ifndef HELLOESP_NATIVE_H
#define HELLOESP_NATIVE_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

#include "defines.h"

#include "screen.h"

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

////////////////////////////////////////////////////////////////

const bool HELLO_DEBUG_wasm_lcd_draw_text = false;
M3Result wasm_lcd_draw_text(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem){
    uint64_t* args = m3ApiOffsetToPtr(_sp++);

    int x = (int)args[0];
    int y = (int)args[1];
    int size = (int)args[2];
    const char* text = (const char *)m3ApiOffsetToPtr(args[3]); // is m3ApiOffsetToPtr still needed?

    if(HELLO_DEBUG_wasm_lcd_draw_text){
        printf("lcd_draw_text called with x:%d y:%d size:%d text: %s\n", x, y, size, text);
    }

    LCD_ShowString(x, y, WHITE, BLACK, size, text, 0);

    return NULL;
}

////////////////////////////////////////////////////////////////////////

const bool HELLO_DEBUG_wasm_esp_add = false;
M3Result wasm_esp_add(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_add blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Ottiene il puntatore allo stack
    uint64_t* stack = m3ApiOffsetToPtr(_sp);

    // Legge i due parametri dallo stack
    int32_t a = m3ApiReadMem32(&stack[0]);
    int32_t b = m3ApiReadMem32(&stack[1]);

    if(HELLO_DEBUG_wasm_esp_add) {
        ESP_LOGI("WASM3", "Add function called with params: a=%d, b=%d", a, b);
    }

    // Calcola la somma
    int32_t result = a + b;

    // Scrive il risultato nello stack (per il valore di ritorno)
    m3ApiWriteMem32(_sp, result);

    if(HELLO_DEBUG_wasm_esp_add) {
        ESP_LOGI("WASM3", "Add function result: %d", result);
    }

    return NULL;  // Ritorna NULL per indicare successo
}

///
///
///

// Definizione della lookup table entry
const WasmFunctionEntry functionTable[] = {
    { 
        .name = (const char*)"esp_printf",           // Function name in WASM
        .func = wasm_esp_printf,    // Pointer to function
        .signature = (const char*)"v(ii)"        // Signature: void (raw_ptr, int32)
    },
    { 
        .name = (const char*)"lcd_draw_text",           // Function name in WASM
        .func = wasm_lcd_draw_text,    // Pointer to function
        .signature = (const char*)"v(iiii)"        // Signature
    },
    { 
        .name = (const char*)"esp_add",           // Function name in WASM
        .func = wasm_esp_add,    // Pointer to function
        .signature = (const char*)"i(ii)"        // Signature
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

/*
Example returns:

// 1. Esempio di funzione che ritorna un intero
M3Result wasm_esp_get_temperature(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_temperature blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Simula lettura temperatura
    int32_t temperature = 25;  // Esempio valore

    // In WASM3, i valori di ritorno vengono pushati sullo stack
    uint64_t* stack = m3ApiOffsetToPtr(_sp);
    m3ApiWriteMem32(stack, temperature);
    
    return NULL;  // NULL indica successo in WASM3
}

// 2. Esempio di funzione che ritorna una stringa
M3Result wasm_esp_get_version(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_version blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Ottieni il puntatore allo stack
    uint64_t* stack = m3ApiOffsetToPtr(_sp);
    
    // Il primo parametro è il puntatore al buffer di destinazione
    char* dest_buffer = m3ApiOffsetToPtr(stack[0]);
    // Il secondo parametro è la dimensione del buffer
    uint32_t buffer_size = m3ApiReadMem32(&stack[1]);

    if (!dest_buffer) {
        ESP_LOGE("WASM3", "Invalid destination buffer");
        return ERROR_MSG_FAILED;
    }

    // Stringa da ritornare
    const char* version = "v1.0.0";
    
    // Copia sicura nel buffer
    strncpy(dest_buffer, version, buffer_size - 1);
    dest_buffer[buffer_size - 1] = '\0';  // Assicura terminazione

    return NULL;
}

// 3. Esempio di funzione che ritorna una struttura
M3Result wasm_esp_get_system_status(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_system_status blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    uint64_t* stack = m3ApiOffsetToPtr(_sp);
    
    // Struttura di esempio per lo stato del sistema
    struct SystemStatus {
        uint32_t heap_free;
        uint32_t temperature;
        uint32_t uptime;
    } status = {
        .heap_free = esp_get_free_heap_size(),
        .temperature = 25,
        .uptime = esp_timer_get_time() / 1000000ULL
    };

    // Il primo parametro è il puntatore alla struttura di destinazione
    void* dest = m3ApiOffsetToPtr(stack[0]);
    if (!dest) {
        ESP_LOGE("WASM3", "Invalid destination pointer");
        return ERROR_MSG_FAILED;
    }

    // Copia la struttura nella memoria WASM
    memcpy(dest, &status, sizeof(struct SystemStatus));

    return NULL;
}

// 4. Esempio di funzione che ritorna un float
M3Result wasm_esp_get_battery_voltage(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_battery_voltage blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Simula lettura voltaggio
    float voltage = 3.7f;  // Esempio valore

    // Ottieni il puntatore allo stack
    uint64_t* stack = m3ApiOffsetToPtr(_sp);
    
    // Scrivi il float sullo stack
    // Nota: potrebbe essere necessario gestire l'allineamento
    m3ApiWriteMem32(stack, *((uint32_t*)&voltage));

    return NULL;
}

M3Result wasm_esp_add(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_add blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Ottiene il puntatore allo stack
    uint64_t* stack = m3ApiOffsetToPtr(_sp);

    // Legge i due parametri dallo stack
    int32_t a = m3ApiReadMem32(&stack[0]);
    int32_t b = m3ApiReadMem32(&stack[1]);

    if(HELLO_DEBUG) {
        ESP_LOGI("WASM3", "Add function called with params: a=%d, b=%d", a, b);
    }

    // Calcola la somma
    int32_t result = a + b;

    // Scrive il risultato nello stack (per il valore di ritorno)
    m3ApiWriteMem32(_sp, result);

    if(HELLO_DEBUG) {
        ESP_LOGI("WASM3", "Add function result: %d", result);
    }

    return NULL;  // Ritorna NULL per indicare successo
}

*/