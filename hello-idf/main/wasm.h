#include <stdio.h>
#include <time.h>
#include <unistd.h>

#include "wasm3.h"
#include "m3_env.h"

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

////////////////////////////////////////////////////////////////////////
// Native functions

m3ApiRawFunction(native_print) {
    m3ApiGetArg(int32_t, value)
    ESP_LOGI(TAG, "WASM called native_print with value: %d", value);
    m3ApiSuccess();
}

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
    result = m3_LinkRawFunction(module, "*", "print", "v(i)", &native_print);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }

    // Execution
    IM3Function f;
    result = m3_FindFunction (&f, runtime, "_start");
    if (result) FATAL("m3_FindFunction: %s", result);

    printf("Running...\n");

    const char* i_argv[2] = { "test.wasm", NULL };

    m3_wasi_context_t* wasi_ctx = m3_GetWasiContext();
    wasi_ctx->argc = 1;
    wasi_ctx->argv = i_argv;

    result = m3_CallV (f);

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