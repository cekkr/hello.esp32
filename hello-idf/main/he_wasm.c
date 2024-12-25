#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "esp_log.h"

#include "he_wasm.h"
#include "he_wasm_native.h"

/////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////

#define FATAL(env, msg, ...) { ESP_LOGI(TAG, "ERROR: Fatal: " msg "\n", ##__VA_ARGS__); goto freeEnv; }

#define HE_WASM_PREALLOCATE false

bool prepare_wasm_execution(const uint8_t* wasm_data, size_t size) {
    // Stima della memoria necessaria (questo valore andrà calibrato)
    size_t estimated_memory = size * 3;  // esempio: 3x il size del modulo
    
    if (!check_memory_available(estimated_memory)) {
        ESP_LOGE(TAG, "Insufficient memory for WASM module");
        return false;
    }
    
    #if HE_WASM_PREALLOCATE
    // Pre-alloca memoria se necessario
    void* pre_allocated = preallocate_wasm_memory(estimated_memory);
    if (!pre_allocated) {
        return false;
    }
    #endif
    
    // Continua con l'esecuzione...
    return true;
}

const bool HELLOESP_RUN_WASM_WDT = ENABLE_WATCHDOG_WASM3 && ENABLE_WATCHDOG;
const bool HELLOESP_WASM_RUNTIME_AT_PARSE = true;
const bool HELLOESP_DEBUG_run_wasm = false;
void run_wasm(uint8_t* wasm, uint32_t fsize, shell_t* shell)
{
    //disable_watchdog();
    if(HELLOESP_RUN_WASM_WDT) { WATCHDOG_ADD }   // Aggiunge il task corrente    

    //watchdog_task_register();

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

    //env->memoryLimit = WASM_STACK_SIZE; // it doesn't exists. find a way if needed

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_NewRuntime\n");
    IM3Runtime runtime = m3_NewRuntime (env, WASM_STACK_SIZE, NULL); //todo: WASM_RUNTIME_MEMORY instead of x*1024
    if (!runtime) FATAL(env, "m3_NewRuntime failed");

    //runtime->memory.maxPages = 1;  // Limita a una pagina
    //runtime->memory.numPages = 1;

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_ParseModule\n");
    IM3Module module;
    result = m3_ParseModule (env, &module, wasm, fsize, HELLOESP_WASM_RUNTIME_AT_PARSE ? runtime : NULL); // NULL should runtime... maybe
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
    result = m3_LinkEspWASI_Hello (module, shell); // runtime->modules
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

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: Starting call\n");

    const char* i_argv[] = {"main.wasm", NULL}; //todo: set right wasm name(?)

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_GetWasiContext\n");
    m3_wasi_context_t* wasi_ctx = m3_GetWasiContext();
    wasi_ctx->argc = 1;
    wasi_ctx->argv = i_argv;

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: m3_CallV\n");

    if(f->module->runtime == NULL){
        FATAL(env, "run_wasm: f->module->runtime is null");
    }

    result = m3_CallV(f);

    if (result) FATAL(env, "m3_Call: %s", result);  

    freeEnv:  
    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "Freeing WASM3 context\n");  
        
    if(runtime) m3_FreeRuntime(runtime);           
    if(env) m3_FreeEnvironment(env);
    
    if(HELLOESP_RUN_WASM_WDT){ 
        WATCHDOG_END
    }   

    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "run_wasm: end of function"); 
}

// WASM3 Task
void wasm_task(void* pvParameters) {
    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "Calling wasm_task");

    wasm_task_params_t* params = (wasm_task_params_t*)pvParameters;
    
    // Esegui WASM in un contesto isolato
    run_wasm(params->wasm_data, params->wasm_size, params->shell);
    
    if(HELLOESP_DEBUG_run_wasm) ESP_LOGI(TAG, "wasm_task: after run_wasm execution");

    // Libera la memoria
    free(params->wasm_data);
    free(params);
    
    // Elimina la task
    vTaskDelete(NULL);
}
