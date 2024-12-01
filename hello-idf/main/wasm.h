#ifndef HELLOESP_WASM
#define HELLOESP_WASM

#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "esp_log.h"

#include "wasm3.h"
#include "m3_env.h"

#include "wasm_native.h"


////////////////////////////////////////////////////////////////////////

#include "m3_core.h"

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

// Definizione della task e configurazione
#define WASM_STACK_SIZE (64*1024)  // Esempio di dimensione stack
#define WASM_TASK_PRIORITY 5

typedef struct {
    uint8_t* wasm_data;
    size_t wasm_size;
} wasm_task_params_t;

////////////////////////////////////////////////////////////////////////
// Native functions

/*m3ApiRawFunction(native_print) {
    m3ApiGetArg(int32_t, value)
    ESP_LOGI(TAG, "WASM called native_print with value: %d", value);
    m3ApiSuccess();
}*/

////////////////////////////////////////////////////////////////

#define FATAL(msg, ...) { ESP_LOGI(TAG, "ERROR: Fatal: " msg "\n", ##__VA_ARGS__); return; }

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

static void run_wasm(uint8_t* wasm, uint32_t fsize)
{
    M3Result result = m3Err_none;

    // Prima verifica la disponibilità di memoria
    if (!prepare_wasm_execution(wasm, fsize)) {
        FATAL("failed to prepare memory for WASM execution");
        return;
    }

    printf("Loading WebAssembly...\n");
    IM3Environment env = m3_NewEnvironment ();
    if (!env) FATAL("m3_NewEnvironment failed");

    IM3Runtime runtime = m3_NewRuntime (env, 64*1024, NULL); //todo: WASM_RUNTIME_MEMORY instead of x*1024
    if (!runtime) FATAL("m3_NewRuntime failed");

    runtime->memory.maxPages = 1;  // Limita a una pagina
    runtime->memory.numPages = 1;

    IM3Module module;
    result = m3_ParseModule (env, &module, wasm, fsize);
    if (result) FATAL("m3_ParseModule: %s", result);

    result = m3_LoadModule (runtime, module);
    if (result) FATAL("m3_LoadModule: %s", result);

    ESP_LOGI(TAG, "run_wasm: m3_LinkEspWASI");
    result = m3_LinkEspWASI (runtime->modules);
    if (result) FATAL("m3_LinkEspWASI: %s", result);

    // Linking native functions
    // Link delle funzioni native
    /*result = m3_LinkRawFunction(module, "*", "print", "v(i)", &native_print);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }*/

    result = m3_LinkRawFunction(module, "env", "esp_printf", "v(ii)", &wasm_esp_printf);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }

    // Execution
    IM3Function f;
    result = m3_FindFunction(&f, runtime, "__original_main");
    if (result) FATAL("m3_FindFunction: %s", result);

    printf("Running WASM...\n");

    const char* i_argv[] = {"main.wasm", NULL}; //todo: set right wasm name(?)

    m3_wasi_context_t* wasi_ctx = m3_GetWasiContext();
    wasi_ctx->argc = 1;
    wasi_ctx->argv = i_argv;

    result = m3_CallV(f);

    if (result) FATAL("m3_Call: %s", result);
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