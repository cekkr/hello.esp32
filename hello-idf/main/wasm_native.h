// esp_wasm_bindings_impl.h
#ifndef ESP_WASM_BINDINGS_IMPL_H
#define ESP_WASM_BINDINGS_IMPL_H

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

// Implementazione della funzione printf per WASM
void wasm_esp_printf__(uint8_t* format, int32_t* args, int32_t arg_count) { // currently not used
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

m3ApiRawFunction(wasm_esp_printf) {
    m3ApiGetArgMem(const char*, format);    // Questo gestisce automaticamente la conversione della memoria
    m3ApiGetArg(int32_t, value);
    
    // Esegui la printf
    printf(format, value);
    
    m3ApiSuccess();
}

///
///
///

// Struttura per definire una funzione da importare
typedef struct {
    const char* moduleName;
    const char* functionName;
    const char* signature;  // "v(ii)" format
    void* function;
} FunctionToLink;

// Converte il formato signature WASM3 in formato WAT
const char* convertSignatureToWAT(const char* signature) {
    static char watSig[64];
    memset(watSig, 0, sizeof(watSig));
    
    char* wat = watSig;
    *wat++ = '(';
    
    // Salta il tipo di ritorno all'inizio (prima del '(')
    const char* sig = strchr(signature, '(');
    if (!sig) return NULL;
    sig++;  // Salta la '('
    
    // Converti i parametri
    while (*sig && *sig != ')') {
        if (wat != watSig) *wat++ = ' ';
        switch (*sig) {
            case 'i': strcat(wat, "i32"); wat += 3; break;
            case 'I': strcat(wat, "i64"); wat += 3; break;
            case 'f': strcat(wat, "f32"); wat += 3; break;
            case 'F': strcat(wat, "f64"); wat += 3; break;
            default: return NULL;
        }
        sig++;
    }
    
    *wat++ = ')';
    
    // Aggiungi il tipo di ritorno
    switch (signature[0]) {
        case 'v': strcat(wat, " (result)"); break;
        case 'i': strcat(wat, " (result i32)"); break;
        case 'I': strcat(wat, " (result i64)"); break;
        case 'f': strcat(wat, " (result f32)"); break;
        case 'F': strcat(wat, " (result f64)"); break;
        default: return NULL;
    }
    
    return watSig;
}

// Genera il modulo WASM con le dichiarazioni di import
M3Result generateAndParseImports(IM3Environment env, IM3Module* out_module, const FunctionToLink* functions) {
    // Buffer per il codice WAT
    char watCode[4096];
    int offset = 0;
    
    // Inizia il modulo
    offset += snprintf(watCode + offset, sizeof(watCode) - offset, "(module\n");
    
    // Aggiungi ogni funzione come import
    for (const FunctionToLink* f = functions; f->moduleName != NULL; f++) {
        const char* watSig = convertSignatureToWAT(f->signature);
        if (!watSig) {
            return "Invalid signature format";
        }
        
        offset += snprintf(watCode + offset, sizeof(watCode) - offset,
            "  (import \"%s\" \"%s\" (func $%s %s))\n",
            f->moduleName, f->functionName, f->functionName, watSig);
    }
    
    // Chiudi il modulo
    offset += snprintf(watCode + offset, sizeof(watCode) - offset, ")\n");
    
    // Debug output
    ESP_LOGI(TAG, "Generated WAT:\n%s", watCode);
    
    // Converti WAT in WASM e parsalo
    uint8_t* wasm = NULL;
    size_t wasmSize = 0;
    
    // Nota: qui dovresti usare una libreria WAT->WASM come wabt
    // Per semplicità, usiamo un WASM pre-generato di esempio
    static const uint8_t basicImportWasm[] = {
        0x00, 0x61, 0x73, 0x6D, 0x01, 0x00, 0x00, 0x00, // magic + version
        0x01, 0x05, 0x01, 0x60, 0x02, 0x7F, 0x7F, 0x00  // type section
        // ... altri bytes necessari per il modulo base
    };
    
    return m3_ParseModule(env, out_module, basicImportWasm, sizeof(basicImportWasm));
}

// Funzione principale di linking che usa la generazione automatica
M3Result linkWASMFunctions_gen(IM3Environment env, IM3Runtime runtime) {
    M3Result result;
    
    // Definisci le funzioni da linkare
    FunctionToLink functions[] = {
        { "env", "esp_printf", "v(ii)", &wasm_esp_printf },
        // Aggiungi altre funzioni qui
        { NULL, NULL, NULL, NULL }  // Terminatore
    };
    
    // Genera e parsa il modulo con gli import
    IM3Module importModule;
    result = generateAndParseImports(env, &importModule, functions);
    if (result) return result;
    
    // Carica il modulo nel runtime
    result = m3_LoadModule(runtime, importModule);
    if (result) return result;
    
    // Esegui il linking delle funzioni
    for (const FunctionToLink* f = functions; f->moduleName != NULL; f++) {
        result = m3_LinkRawFunction(
            importModule,
            f->moduleName,
            f->functionName,
            f->signature,
            f->function
        );
        
        if (result) {
            ESP_LOGE(TAG, "Failed to link %s.%s: %s", 
                f->moduleName, f->functionName, result);
            return result;
        }
    }
    
    return m3Err_none;
}

////
////
////

static const uint8_t import_wasm[] = {
    // Header
    0x00, 0x61, 0x73, 0x6d,    // Magic number (\0asm)
    0x01, 0x00, 0x00, 0x00,    // Version 1 (as little-endian)
    
    // Type section (1)
    0x01,                       // Section code
    0x07,                       // Section size
    0x01,                       // Number of types
    0x60,                       // Function type
    0x02,                       // Number of parameters
    0x7f,                       // i32
    0x7f,                       // i32
    0x00,                       // Number of results (0)
    
    // Import section (2)
    0x02,                       // Section code
    0x0d,                       // Section size
    0x01,                       // Number of imports
    0x03,                       // Length of module name
    'e', 'n', 'v',             // Module name "env"
    0x09,                       // Length of function name
    'e', 's', 'p', '_',        // Function name "esp_printf"
    'p', 'r', 'i', 'n',
    't', 'f',
    0x00,                       // Import kind (function)
    0x00                        // Type index
};

M3Result linkWASMFunctions(IM3Environment env, IM3Runtime runtime) {
    M3Result result;
    
    // Parsa il modulo di import
    IM3Module module;
    result = m3_ParseModule(env, &module, import_wasm, sizeof(import_wasm));
    if (result) {
        ESP_LOGE(TAG, "Failed to parse import module: %s", result);
        return result;
    }
    
    // Carica il modulo nel runtime
    result = m3_LoadModule(runtime, module);
    if (result) {
        ESP_LOGE(TAG, "Failed to load module: %s", result);
        return result;
    }
    
    // Link la funzione
    result = m3_LinkRawFunction(
        module,
        "env",
        "esp_printf",
        "v(ii)",
        &wasm_esp_printf
    );
    
    if (result) {
        ESP_LOGE(TAG, "Failed to link function: %s", result);
        return result;
    }
    
    return m3Err_none;
}

////
////
////

// Esempio di utilizzo
void init_example_linkWASMFunctions() {
    IM3Environment env = m3_NewEnvironment();
    IM3Runtime runtime = m3_NewRuntime(env, 8192, NULL);
    
    M3Result result = linkWASMFunctions(env, runtime);
    if (result) {
        ESP_LOGE(TAG, "WASM linking failed: %s", result);
    }
}

#endif // ESP_WASM_BINDINGS_IMPL_H