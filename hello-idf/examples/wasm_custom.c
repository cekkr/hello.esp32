#include "esp_system.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wasm3.h"
#include "m3_env.h"

#define TAG "WASM"

// Funzioni native che vogliamo esporre a WASM
m3_wasm_t* g_wasm_ctx = NULL;

// Esempio di funzione nativa per controllare un LED
m3ApiRawFunction(native_toggle_led) {
    m3ApiGetArg(uint32_t, pin)
    m3ApiGetArg(uint32_t, state)
    
    // Implementazione della funzione nativa
    gpio_set_level((gpio_num_t)pin, state);
    
    m3ApiSuccess();
}

// Esempio di funzione che legge un sensore
m3ApiRawFunction(native_read_sensor) {
    m3ApiGetArg(uint32_t, sensor_type)
    
    // Implementazione della lettura del sensore
    int value = 0;
    switch(sensor_type) {
        case 0: // esempio: temperatura
            value = read_temperature(); // tua funzione
            break;
        case 1: // esempio: umidità
            value = read_humidity();    // tua funzione
            break;
    }
    
    m3ApiReturn(value);
}

// Struttura per definire le funzioni da importare
typedef struct {
    const char* module;
    const char* name;
    const char* signature;
    M3RawFunction function;
} WasmFunctionBinding;

// Array di funzioni native da esporre a WASM
const WasmFunctionBinding native_functions[] = {
    {"env", "toggle_led", "v(ii)", &native_toggle_led},
    {"env", "read_sensor", "i(i)", &native_read_sensor},
    // Aggiungi altre funzioni qui
    {0}  // Terminatore
};

// Funzione per linkare le funzioni native
M3Result link_native_functions(IM3Module module) {
    M3Result result = m3Err_none;
    
    for (const WasmFunctionBinding* binding = native_functions; binding->module; binding++) {
        result = m3_LinkRawFunction(
            module, 
            binding->module, 
            binding->name, 
            binding->signature, 
            binding->function
        );
        
        if (result) {
            ESP_LOGE(TAG, "Linking failed for %s.%s: %s", 
                     binding->module, binding->name, result);
            return result;
        }
    }
    
    return result;
}

// Task WASM aggiornato con supporto per funzioni native
void wasm_task(void *pvParameters) {
    IM3Environment env = m3_NewEnvironment();
    if (!env) {
        ESP_LOGE(TAG, "Failed to create environment");
        vTaskDelete(NULL);
        return;
    }

    IM3Runtime runtime = m3_NewRuntime(env, 8192, NULL);
    if (!runtime) {
        ESP_LOGE(TAG, "Failed to create runtime");
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Il tuo bytecode WASM
    uint8_t* wasm_bytes = /* il tuo bytecode */;
    uint32_t wasm_size = /* dimensione */;

    IM3Module module;
    M3Result result = m3_ParseModule(env, &module, wasm_bytes, wasm_size);
    if (result) {
        ESP_LOGE(TAG, "Parse failed: %s", result);
        goto cleanup;
    }

    // Linkare le funzioni native
    result = link_native_functions(module);
    if (result) {
        ESP_LOGE(TAG, "Linking native functions failed: %s", result);
        goto cleanup;
    }

    result = m3_LoadModule(runtime, module);
    if (result) {
        ESP_LOGE(TAG, "Load failed: %s", result);
        goto cleanup;
    }

    // Memorizza il contesto per l'uso nelle funzioni native
    g_wasm_ctx = runtime;

    // Trova ed esegue la funzione main
    IM3Function f;
    result = m3_FindFunction(&f, runtime, "main");
    if (result) {
        ESP_LOGE(TAG, "Find main failed: %s", result);
    } else {
        result = m3_Call(f, 0, NULL);
        if (result) {
            ESP_LOGE(TAG, "Call main failed: %s", result);
        }
    }

    cleanup:{
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        g_wasm_ctx = NULL;
        vTaskDelete(NULL);
    }
}