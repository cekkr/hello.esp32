#include "he_wasm_native.h"

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

#include "he_defines.h"
#include "he_settings.h"
#include "he_screen.h"

#include "wasm3.h"
#include "m3_pointers.h"
#include "m3_segmented_memory.h"

#include "he_wasm_native_stdclib.h"
#include "wasm3_defs.h"

///
///
///

const char* ERROR_MSG_NULLS = "wasm_esp_printf: runtime or _mem is null";
const char* ERROR_MSG_FAILED = "wasm_esp_printf: failed";

#define ArgAccess(ptr) m3_ResolvePointer(_mem, CAST_PTR ptr)

const bool HELLO_DEBUG_wasm_esp_printf = false;
WASM_NATIVE wasm_esp_printf(IM3Runtime runtime, IM3ImportContext *ctx, m3stack_t _sp, IM3Memory _mem) {
    bool runtime_null = (runtime == NULL);
    bool mem_null = (_mem == NULL);
    
    if (runtime_null || mem_null) {
        //ESP_LOGW("WASM3", "wasm_esp_printf blocked: runtime=%p, _sp=%p, mem=%p", runtime, _sp, _mem);
        return m3Err_nullMemory;
    }

    int narg = 0;
    uint64_t* args = (uint64_t*) m3ApiOffsetToPtr(CAST_PTR _sp++);

    // Recupera e valida il puntatore al formato
    const char* format = (const char*) m3ApiOffsetToPtr(CAST_PTR args[narg++]);
    if (!format) {
        ESP_LOGE("WASM3", "esp_printf: Invalid format string pointer");
        return m3Err_pointerOverflow;
    }

    uint64_t* vargs = (uint64_t*) m3ApiOffsetToPtr(CAST_PTR args[narg++]); //*((uint64_t**) args[narg++]);

    if(HELLO_DEBUG_wasm_esp_printf) ESP_LOGE("WASM3", "wasm_esp_printf: format(%p): %s", format, format);

    // Array per memorizzare gli argomenti processati
    union {
        int32_t i;
        uint32_t u;
        float f;
        const char* s;
        void* p;
    } sargs[16];  // Supporta fino a 16 argomenti
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

                switch (*fmt_ptr) {
                    case 'd': case 'i': case 'u': case 'x': case 'X':
                        //todo: implement every format
                        sargs[arg_count].i = *(int64_t*)vargs;                        
                        break;
                    case 'f':
                        // Gestione float con controllo del tipo
                        sargs[arg_count].f = *(float*)vargs;              
                        break;
                    case 's': {
                        // Gestione stringhe con validazione del puntatore
                        void* ptr = (void*) m3ApiOffsetToPtr(CAST_PTR vargs);

                        // is double resolve needed in case of string?
                        if(IsValidMemoryAccess(_mem, CAST_PTR ptr, 1)){
                            ESP_LOGW("WASM3", "yes, double resolve needed in case of string");
                            ptr = (void*) m3ApiOffsetToPtr(CAST_PTR ptr);                            
                        }

                        sargs[arg_count].s = malloc(sizeof(char) * LOG_BUFFER_SIZE);
                        m3_memcpy(_mem, sargs[arg_count].s, ptr,  strlen(ptr));

                        if (!sargs[arg_count].s) {
                            ESP_LOGE("WASM3", "esp_printf: Invalid string pointer");
                            return ERROR_MSG_FAILED;
                        }
                        break;
                    }
                    case 'p': {
                        // Gestione puntatori                        
                        sargs[arg_count].p = vargs;
                        break;
                    }                    
                }
                
                vargs += 2; //todo: check for architecture bits size
                arg_count++;
            }
        }
        fmt_ptr++;
    }

    // Debug logging
    if(HELLO_DEBUG_wasm_esp_printf) ESP_LOGD("WASM3", "esp_printf: Format: %s, ArgCount: %d", format, arg_count);

    ///
    /// Print result
    ///

    //todo: malloc it
    char formatted_output[512];  // Increased buffer for safety    

    // Variabili per la formattazione dell'output
    char temp_buffer[sizeof(formatted_output)];
    char *out_ptr = formatted_output;
    size_t remaining = sizeof(formatted_output);
    int current_arg = 0;
    
    // Processa la stringa di formato carattere per carattere
    fmt_ptr = format;
    while (*fmt_ptr && remaining > 0) {
        if (*fmt_ptr != '%') {
            // Copia caratteri normali
            *out_ptr++ = *fmt_ptr++;
            remaining--;
            continue;
        }
        
        // Gestisce il carattere %
        fmt_ptr++;
        if (*fmt_ptr == '%') {
            *out_ptr++ = '%';
            fmt_ptr++;
            remaining--;
            continue;
        }
        
        if (current_arg >= arg_count) {
            ESP_LOGE("WASM3", "esp_printf: Not enough arguments for format string");
            return ERROR_MSG_FAILED;
        }
        
        // Formatta l'argomento corrente in base al suo tipo
        int write_result = 0;
        switch (*fmt_ptr) {
            case 'd':
            case 'i':
                write_result = snprintf(temp_buffer, remaining, "%d", sargs[current_arg].i);
                break;
            case 'u':
                write_result = snprintf(temp_buffer, remaining, "%u", sargs[current_arg].u);
                break;
            case 'x':
                write_result = snprintf(temp_buffer, remaining, "%x", sargs[current_arg].u);
                break;
            case 'X':
                write_result = snprintf(temp_buffer, remaining, "%X", sargs[current_arg].u);
                break;
            case 'f':
                write_result = snprintf(temp_buffer, remaining, "%f", sargs[current_arg].f);
                break;
            case 's':
                write_result = snprintf(temp_buffer, remaining, "%s", sargs[current_arg].s);
                break;
            case 'p':
                write_result = snprintf(temp_buffer, remaining, "%p", sargs[current_arg].p);
                break;
            default:
                ESP_LOGE("WASM3", "esp_printf: Unsupported format specifier: %c", *fmt_ptr);
                return ERROR_MSG_FAILED;
        }
        
        if (write_result < 0 || write_result >= remaining) {
            ESP_LOGE("WASM3", "esp_printf: Buffer overflow while formatting argument");
            return ERROR_MSG_FAILED;
        }
        
        // Copia il risultato nel buffer di output
        strcpy(out_ptr, temp_buffer);
        out_ptr += write_result;
        remaining -= write_result;
        
        current_arg++;
        fmt_ptr++;
    }
    
    // Verifica che ci sia spazio per il terminatore e finalizza la stringa
    if (remaining > 0) {
        *out_ptr = '\0';
        // Output del risultato finale
        ESP_LOGI("WASM3", "%s", formatted_output);
        
        // Libera la memoria allocata per le stringhe
        for (int i = 0; i < arg_count; i++) {
            const char* fmt_scan = format;
            int format_spec_count = 0;
            while (*fmt_scan && format_spec_count < i) {
                if (*fmt_scan == '%' && *(fmt_scan + 1) != '%') {
                    format_spec_count++;
                }
                fmt_scan++;
            }
            if (*fmt_scan == '%' && *(fmt_scan + 1) == 's' && sargs[i].s != NULL) {
                free((void*)sargs[i].s);
            }
        }
    } else {
        ESP_LOGE("WASM3", "esp_printf: Output buffer overflow");
        return ERROR_MSG_FAILED;
    }

    return NULL;
}

////////////////////////////////////////////////////////////////

const bool HELLO_DEBUG_wasm_lcd_draw_text = false;
WASM_NATIVE wasm_lcd_draw_text(IM3Runtime runtime, IM3ImportContext *ctx, m3stack_t _sp, IM3Memory _mem){
    uint64_t* args = (uint64_t*) m3ApiOffsetToPtr(CAST_PTR _sp++);

    int x = (int)args[0];
    int y = (int)args[1];
    int size = (int)args[2];
    const char* text = (const char *)m3ApiOffsetToPtr((mos)args[3]); // is m3ApiOffsetToPtr still needed?

    if(HELLO_DEBUG_wasm_lcd_draw_text){
        printf("lcd_draw_text called with x:%d y:%d size:%d text: %s\n", x, y, size, text);
    }

    LCD_ShowString(x, y, WHITE, BLACK, size, text, 0);

    return NULL;
}

////////////////////////////////////////////////////////////////////////

const bool HELLO_DEBUG_wasm_esp_add = false;
WASM_NATIVE wasm_esp_add(IM3Runtime runtime, IM3ImportContext *ctx, m3stack_t _sp, IM3Memory _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_add blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }
    
    m3_GetArgs();
    m3_GetReturn(int32_t);    
    m3_GetArg(int32_t, a);
    m3_GetArg(int32_t, b);

    if(HELLO_DEBUG_wasm_esp_add) {
        ESP_LOGI("WASM3", "esp_add: Add function called with params: a=%d, b=%d, return: %p", a, b, raw_return);
    }

    // Calcola la somma
    int32_t result = a + b;

    // Scrive il risultato nello stack (per il valore di ritorno)
    //m3ApiWriteMem32(raw_return, result); // oppure linea successiva
    *raw_return = result;

    if(HELLO_DEBUG_wasm_esp_add) {
        ESP_LOGI("WASM3", "Add function result: %d", result);
    }

    return NULL;  // Ritorna NULL per indicare successo
}

////////////////////////////////////////////////////////////////

const bool HELLO_DEBUG_wasm_esp_read_serial = false;
WASM_NATIVE wasm_esp_read_serial(IM3Runtime runtime, IM3ImportContext *ctx, m3stack_t _sp, IM3Memory _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_read_serial blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    m3ApiReturnType  (char*)

    settings_t* settings = get_main_settings();

    if(HELLO_DEBUG_wasm_esp_read_serial) ESP_LOGI("WASM3", "esp_read_serial: setting serial_wasm_read true");
    settings->_serial_wasm_read = true;

    while(settings->_serial_wasm_read){
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    if(HELLO_DEBUG_wasm_esp_read_serial) ESP_LOGI("WASM3", "esp_read_serial: serial_wasm_read setted to false");

    if(settings->_serial_wasm_read_string){       
        void* retStr = m3_Malloc(_mem, settings->_serial_wasm_read_string_len*sizeof(char));
        M3Result res = m3_memcpy(_mem, retStr, settings->_serial_wasm_read_string, settings->_serial_wasm_read_string_len);
        
        if(HELLO_DEBUG_wasm_esp_read_serial){ 
            ESP_LOGI("WASM3", "esp_read_serial: retStr: %p (len: %lu)", retStr, settings->_serial_wasm_read_string_len); 
            ESP_LOGI("WASM3", "esp_read_serial: retStr content: %s", (char*)m3_ResolvePointer(_mem, CAST_PTR retStr));  // it works
        }

        if(res != NULL){
            ESP_LOGE("WASM3", "wasm_esp_read_serial: error while copying string to memory (%s)", res);
            m3_free(_mem, retStr);
            return res;
        }

        *raw_return = retStr;
        
        m3_free(_mem, settings->_serial_wasm_read_string);
        settings->_serial_wasm_read_string = NULL;
    }
    else {
        *raw_return = NULL;
        ESP_LOGW("WASM3", "wasm_esp_read_serial had NULL serial_wasm_read_string");
    }

    return NULL;
}

///
///
///

// Definizione della lookup table entry
const WasmFunctionEntry functionTable[] = {
    { 
        .name = "esp_printf",           // Function name in WASM
        .func = wasm_esp_printf,    // Pointer to function
        .signature = "v(pp)"        // Signature: void (raw_ptr, size_t)
    },
    { 
        .name = "lcd_draw_text",           // Function name in WASM
        .func = wasm_lcd_draw_text,    // Pointer to function
        .signature = "v(iiip)"        // Signature
    },
    { 
        .name = "esp_add",           // Function name in WASM
        .func = wasm_esp_add,    // Pointer to function
        .signature = "i(ii)"        // Signature
    },
    {
        .name = "esp_read_serial",           // Function name in WASM
        .func = wasm_esp_read_serial,    // Pointer to function
        .signature = "p()"        // Signature
    }
    // Altre funzioni possono essere aggiunte qui
};

const bool HELLOESP_WASM_REGISTER_CLIB = false;
M3Result registerNativeWASMFunctions(IM3Module module, m3_wasi_context_t *ctx){
    M3Result result;

    if(HELLOESP_WASM_REGISTER_CLIB){
        // C Standard Library
        result = RegisterStandardCLibFunctions(module, ctx);
        if (result) {
            return result;
        }
    }

    // HelloESP Functions
    result = RegisterWasmFunctions(module, functionTable, sizeof(functionTable)/sizeof(functionTable[0]), ctx);
    if (result) {
        ESP_LOGE(TAG, "Failed to register functions: %s", result);
    }

    return result;
}

/*
Example returns:

// 1. Esempio di funzione che ritorna un intero
M3Result wasm_esp_get_temperature(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_temperature blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Simula lettura temperatura
    int32_t temperature = 25;  // Esempio valore

    // In WASM3, i valori di ritorno vengono pushati sullo stack
    mos stack = m3ApiOffsetToPtr(_sp);
    m3ApiWriteMem32(stack, temperature);
    
    return NULL;  // NULL indica successo in WASM3
}

// 2. Esempio di funzione che ritorna una stringa
M3Result wasm_esp_get_version(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_version blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Ottieni il puntatore allo stack
    mos stack = m3ApiOffsetToPtr(_sp);
    
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
M3Result wasm_esp_get_system_status(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_system_status blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    mos stack = m3ApiOffsetToPtr(_sp);
    
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
M3Result wasm_esp_get_battery_voltage(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_get_battery_voltage blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Simula lettura voltaggio
    float voltage = 3.7f;  // Esempio valore

    // Ottieni il puntatore allo stack
    mos stack = m3ApiOffsetToPtr(_sp);
    
    // Scrivi il float sullo stack
    // Nota: potrebbe essere necessario gestire l'allineamento
    m3ApiWriteMem32(stack, *((uint32_t*)&voltage));

    return NULL;
}

M3Result wasm_esp_add(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    if (!runtime || !_mem) {
        ESP_LOGW("WASM3", "wasm_esp_add blocked: runtime=%p, mem=%p", runtime, _mem);
        return ERROR_MSG_NULLS;
    }

    // Ottiene il puntatore allo stack
    mos stack = m3ApiOffsetToPtr(_sp);

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