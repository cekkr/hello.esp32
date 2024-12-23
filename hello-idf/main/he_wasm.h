#ifndef HELLOESP_WASM_H
#define HELLOESP_WASM_H
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "esp_log.h"
#include "he_defines.h"
#include "he_device.h"
#include "wasm3.h"
#include "m3_env.h"
#include "m3_api_esp_wasi.h"
//#include "m3_core.h"

/*typedef struct m3_wasi_context
{
    i32                     exit_code;
    u32                     argc;
    ccstr_t *               argv;
} m3_wasi_context_t;*/

typedef struct wasm_task_params{
    uint8_t* wasm_data;
    size_t wasm_size;
} wasm_task_params_t;

typedef struct {
    SemaphoreHandle_t memMutex;
    IM3Runtime runtime;
    IM3Environment env;
    // Puoi aggiungere altri campi necessari
} Wasm3Context;


bool prepare_wasm_execution(const uint8_t* wasm_data, size_t size);
void run_wasm(uint8_t* wasm, uint32_t fsize);
void wasm_task(void* pvParameters);

#endif // HELLOESP_WASM