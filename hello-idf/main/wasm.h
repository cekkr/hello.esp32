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
#define WASM_STACK_SIZE (32*1024)  // Esempio di dimensione stack
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

#define FATAL(msg, ...) { printf("Fatal: " msg "\n", ##__VA_ARGS__); return; }

static void run_wasm(uint8_t* wasm, uint32_t fsize)
{
    M3Result result = m3Err_none;

    printf("Loading WebAssembly...\n");
    IM3Environment env = m3_NewEnvironment ();
    if (!env) FATAL("m3_NewEnvironment failed");

    IM3Runtime runtime = m3_NewRuntime (env, 8*1024, NULL);
    if (!runtime) FATAL("m3_NewRuntime failed");

    IM3Module module;
    result = m3_ParseModule (env, &module, wasm, fsize);
    if (result) FATAL("m3_ParseModule: %s", result);

    result = m3_LoadModule (runtime, module);
    if (result) FATAL("m3_LoadModule: %s", result);

    result = m3_LinkEspWASI (runtime->modules);
    if (result) FATAL("m3_LinkEspWASI: %s", result);

    // Linking native functions
    // Link delle funzioni native
    /*result = m3_LinkRawFunction(module, "*", "print", "v(i)", &native_print);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }*/

    result = m3_LinkRawFunction(module, "env", "esp_printf", "v(i*i)", &wasm_esp_printf);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }

    // Execution
    IM3Function f;
    result = m3_FindFunction(&f, runtime, "main");
    if (result) FATAL("m3_FindFunction: %s", result);

    printf("Running...\n");

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