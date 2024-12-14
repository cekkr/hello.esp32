#ifndef HELLOESP_WASM_H
#define HELLOESP_WASM_H

#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "esp_log.h"

#include "wasm3.h"
#include "m3_env.h"
#include "m3_api_esp_wasi.h"

#include "wasm_native.h"


////////////////////////////////////////////////////////////////////////
//#include "m3_core.h"

/*
d_m3BeginExternC

typedef struct m3_wasi_context_t
{
    i32                     exit_code;
    u32                     argc;
    ccstr_t *               argv;
} m3_wasi_context_t;

M3Result    m3_LinkEspWASI     (IM3Module io_module);

m3_wasi_context_t* m3_GetWasiContext();

////////////////////////////////////////////////////////////////
*/

// Definizione della task e configurazione
#define WASM_STACK_SIZE (32*1024)  // Esempio di dimensione stack
#define WASM_TASK_PRIORITY 5

typedef struct {
    uint8_t* wasm_data;
    size_t wasm_size;
} wasm_task_params_t;

/////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////

#define FATAL(env, msg, ...) { ESP_LOGI(TAG, "ERROR: Fatal: " msg "\n", ##__VA_ARGS__); if(env != NULL) m3_FreeEnvironment(env); return; }

bool prepare_wasm_execution(const uint8_t* wasm_data, size_t size) {
    // Stima della memoria necessaria (questo valore andrà calibrato)
    size_t estimated_memory = size * 3;  // esempio: 3x il size del modulo
    
    if (!check_memory_available(estimated_memory)) {
        ESP_LOGE(TAG, "Insufficient memory for WASM module");
        return false;
    }
    
    // Pre-alloca memoria se necessario
    void* pre_allocated = preallocate_wasm_memory(estimated_memory);
    if (!pre_allocated) {
        return false;
    }
    
    // Continua con l'esecuzione...
    return true;
}

static const bool HELLOESP_DEBUG_run_wasm = true;
static void run_wasm(uint8_t* wasm, uint32_t fsize)
{
    M3Result result = m3Err_none;

    // Prima verifica la disponibilità di memoria
    if (!prepare_wasm_execution(wasm, fsize)) {
        FATAL(NULL, "failed to prepare memory for WASM execution");
        return;
    }

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "Loading WebAssembly...\n");

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_NewEnvironment\n");
    IM3Environment env = m3_NewEnvironment ();
    if (!env) FATAL(env, "m3_NewEnvironment failed");

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_NewRuntime\n");
    IM3Runtime runtime = m3_NewRuntime (env, 64*1024, NULL); //todo: WASM_RUNTIME_MEMORY instead of x*1024
    if (!runtime) FATAL(env, "m3_NewRuntime failed");

    //runtime->memory.maxPages = 1;  // Limita a una pagina
    //runtime->memory.numPages = 1;

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_ParseModule\n");
    IM3Module module;
    result = m3_ParseModule (env, &module, wasm, fsize);
    if (result) FATAL(env, "m3_ParseModule: %s", result);  

    module->name = "env";  
    
    /*if(false){ // WASI linking (old school version)
        ESP_LOGI(TAG, "run_wasm: m3_LinkEspWASI"); 
        result = m3_LinkEspWASI (module); // runtime->modules
        if (result) FATAL(env, "m3_LinkEspWASI: %s", result);
    }*/

    // Finally, load the module
    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_LoadModule\n");
    result = m3_LoadModule (runtime, module);
    if (result) FATAL(env, "m3_LoadModule: %s", result);

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_LinkEspWASI_Hello\n");
    result = m3_LinkEspWASI_Hello (runtime->modules);
    if (result) FATAL(env, "m3_LinkEspWASI: %s", result);

    // Linking native functions
    // Link delle funzioni native
    //result = linkWASMFunctions(env, runtime, module);
    //result = justLinkWASMFunctions(module);

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: registerNativeWASMFunctions\n");
    result = registerNativeWASMFunctions(module);
    if (result) FATAL(env, "registerNativeWASMFunctions: %s", result);

    /*result = m3_LinkRawFunction(module, "env", "esp_printf", "v(ii)", &wasm_esp_printf);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }*/

    // Execution
    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_FindFunction\n");
    IM3Function f;
    result = m3_FindFunction(&f, runtime, "start");
    if (result) FATAL(env, "m3_FindFunction: %s", result);

    ESP_LOGI(TAG, "run_wasm: Starting call\n");

    const char* i_argv[] = {"main.wasm", NULL}; //todo: set right wasm name(?)

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_GetWasiContext\n");
    m3_wasi_context_t* wasi_ctx = m3_GetWasiContext();
    wasi_ctx->argc = 1;
    wasi_ctx->argv = i_argv;

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_CallV\n");
    result = m3_CallV(f);

    if (result) FATAL(env, "m3_Call: %s", result);    
}

void app_main_wasm3(void) // just for example
{
    printf("\nWasm3 v" M3_VERSION " on " CONFIG_IDF_TARGET ", build " __DATE__ " " __TIME__ "\n");

    clock_t start = clock();
    //run_wasm();
    clock_t end = clock();

    printf("Elapsed: %ld ms\n", (end - start)*1000 / CLOCKS_PER_SEC);

    sleep(3);
    printf("Restarting...\n\n\n");
    esp_restart();
}

// WASM3 Task
static void wasm_task(void* pvParameters) {
    ESP_LOGI(TAG, "Calling wasm_task");

    wasm_task_params_t* params = (wasm_task_params_t*)pvParameters;
    
    // Esegui WASM in un contesto isolato
    run_wasm(params->wasm_data, params->wasm_size);
    
    // Libera la memoria
    free(params->wasm_data);
    free(params);
    
    // Elimina la task
    vTaskDelete(NULL);
}

#endif // HELLOESP_WASM