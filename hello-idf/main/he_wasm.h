#ifndef HELLOESP_WASM_H
#define HELLOESP_WASM_H
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "esp_log.h"

#include "he_cmd.h"
#include "wasm3.h"

//#include "m3_core.h"

typedef struct wasm_task_params{
    uint8_t* wasm_data;
    size_t wasm_size;
    shell_t * shell;
} wasm_task_params_t;

typedef struct {
    SemaphoreHandle_t memMutex;
    IM3Runtime runtime;
    IM3Environment env;
    // Puoi aggiungere altri campi necessari
} Wasm3Context;


bool prepare_wasm_execution(const uint8_t* wasm_data, size_t size);
void run_wasm(uint8_t* wasm, uint32_t fsize, shell_t* shell);
void wasm_task(void* pvParameters);

#endif // HELLOESP_WASM