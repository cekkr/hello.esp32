// Includere le librerie necessarie
#include "esp_system.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wasm3.h"
#include "m3_env.h"

// Dimensione dello stack per il runtime WASM
#define WASM_STACK_SIZE 1024
#define TAG "WASM"

// Funzione per inizializzare il runtime WASM
IM3Environment init_wasm_environment() {
    // Creare l'ambiente WASM
    IM3Environment env = m3_NewEnvironment();
    if (env == NULL) {
        ESP_LOGE(TAG, "Failed to create environment");
        return NULL;
    }
    return env;
}

// Task FreeRTOS per eseguire WASM
void wasm_task(void *pvParameters) {
    // Inizializzare l'ambiente
    IM3Environment env = init_wasm_environment();
    if (env == NULL) {
        vTaskDelete(NULL);
        return;
    }

    // Creare il runtime
    IM3Runtime runtime = m3_NewRuntime(env, WASM_STACK_SIZE, NULL);
    if (runtime == NULL) {
        ESP_LOGE(TAG, "Failed to create runtime");
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Qui inserisci il tuo bytecode WASM compilato
    const uint8_t* wasm_bytes = /* il tuo bytecode WASM */;
    uint32_t wasm_size = /* dimensione del bytecode */;

    // Caricare il modulo WASM
    IM3Module module;
    M3Result result = m3_ParseModule(env, &module, wasm_bytes, wasm_size);
    if (result) {
        ESP_LOGE(TAG, "Failed to parse module: %s", result);
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Caricare il modulo nel runtime
    result = m3_LoadModule(runtime, module);
    if (result) {
        ESP_LOGE(TAG, "Failed to load module: %s", result);
        m3_FreeModule(module);
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Trovare ed eseguire la funzione main
    IM3Function f;
    result = m3_FindFunction(&f, runtime, "main");
    if (result) {
        ESP_LOGE(TAG, "Failed to find main function: %s", result);
    } else {
        result = m3_Call(f, 0, NULL);
        if (result) {
            ESP_LOGE(TAG, "Failed to call main function: %s", result);
        }
    }

    // Pulizia
    m3_FreeRuntime(runtime);
    m3_FreeEnvironment(env);
    vTaskDelete(NULL);
}

// Funzione principale per avviare il task WASM
void start_wasm_runtime() {
    xTaskCreate(wasm_task, "wasm_task", 8192, NULL, 5, NULL);
}