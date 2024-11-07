Ti mostro un esempio completo di come eseguire un modulo WebAssembly su ESP32 usando ESP-IDF.

```cpp
#include <stdio.h>
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wasm3.h"
#include "m3_env.h"

// Tag per i log
static const char* TAG = "WASM";

// Esempio di bytecode WASM (compilato da questo codice AssemblyScript):
/*
export function fibonacci(n: i32): i32 {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}
*/
static const uint8_t wasm_fibonacci[] = {
    0x00, 0x61, 0x73, 0x6D, 0x01, 0x00, 0x00, 0x00, 0x01, 0x06, 0x01, 0x60,
    0x01, 0x7F, 0x01, 0x7F, 0x03, 0x02, 0x01, 0x00, 0x07, 0x0B, 0x01, 0x07,
    0x66, 0x69, 0x62, 0x6F, 0x6E, 0x61, 0x63, 0x69, 0x00, 0x00, 0x0A, 0x1F,
    0x01, 0x1D, 0x00, 0x20, 0x00, 0x41, 0x01, 0x49, 0x04, 0x40, 0x20, 0x00,
    0x0F, 0x0B, 0x20, 0x00, 0x41, 0x01, 0x6B, 0x10, 0x00, 0x20, 0x00, 0x41,
    0x02, 0x6B, 0x10, 0x00, 0x6A, 0x0F, 0x0B
};

// Funzione nativa di esempio che possiamo chiamare da WASM
m3ApiRawFunction(native_print) {
    m3ApiGetArg(int32_t, value)
    ESP_LOGI(TAG, "WASM called native_print with value: %d", value);
    m3ApiSuccess();
}

// Task che esegue il modulo WASM
void wasm_task(void* pvParameters) {
    M3Result result = m3Err_none;

    // Crea un nuovo ambiente WASM
    IM3Environment env = m3_NewEnvironment();
    if (!env) {
        ESP_LOGE(TAG, "Failed to create environment");
        vTaskDelete(NULL);
        return;
    }

    // Crea un nuovo runtime
    IM3Runtime runtime = m3_NewRuntime(env, 1024, NULL);
    if (!runtime) {
        ESP_LOGE(TAG, "Failed to create runtime");
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Carica il modulo WASM
    IM3Module module;
    result = m3_ParseModule(env, &module, wasm_fibonacci, sizeof(wasm_fibonacci));
    if (result) {
        ESP_LOGE(TAG, "Failed to parse module: %s", result);
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Carica il modulo nel runtime
    result = m3_LoadModule(runtime, module);
    if (result) {
        ESP_LOGE(TAG, "Failed to load module: %s", result);
        m3_FreeModule(module);
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Link delle funzioni native
    result = m3_LinkRawFunction(module, "*", "print", "v(i)", &native_print);
    if (result) {
        ESP_LOGE(TAG, "Failed to link native function: %s", result);
    }

    // Trova la funzione fibonacci
    IM3Function fibonacci;
    result = m3_FindFunction(&fibonacci, runtime, "fibonacci");
    if (result) {
        ESP_LOGE(TAG, "Failed to find function: %s", result);
        m3_FreeRuntime(runtime);
        m3_FreeEnvironment(env);
        vTaskDelete(NULL);
        return;
    }

    // Esegui la funzione fibonacci per alcuni valori
    for (int i = 0; i < 10; i++) {
        int32_t ret = 0;
        result = m3_CallV(fibonacci, &ret, i);
        if (result) {
            ESP_LOGE(TAG, "Failed to call function: %s", result);
        } else {
            ESP_LOGI(TAG, "fibonacci(%d) = %d", i, ret);
        }
        vTaskDelay(pdMS_TO_TICKS(1000));  // Attendi 1 secondo tra le chiamate
    }

    // Pulisci
    m3_FreeRuntime(runtime);
    m3_FreeEnvironment(env);
    vTaskDelete(NULL);
}

extern "C" void app_main(void) {
    // Crea il task WASM
    xTaskCreate(wasm_task, "wasm", 32768, NULL, 5, NULL);
}

```

E qui il `CMakeLists.txt` necessario:

```cmake
cmake_minimum_required(VERSION 3.5)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_wasm_example)

# Assicurati che wasm3 sia una dipendenza del progetto
```

E il file `idf_component.yml`:

```yaml
dependencies:
  wasm3:
    git: https://github.com/wasm3/wasm3.git
    path: platforms/esp32
```

Per compilare il codice WebAssembly da eseguire su ESP32, puoi usare AssemblyScript. Ecco il file sorgente (`fibonacci.ts`):

```typescript
export function fibonacci(n: i32): i32 {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}
```

Per compilarlo:
1. Installa AssemblyScript: `npm install -g assemblyscript`
2. Compila: `asc fibonacci.ts -b fibonacci.wasm --optimize`
3. Converti il file `.wasm` in un array C: `xxd -i fibonacci.wasm > fibonacci_wasm.h`

Per eseguire questo esempio:

1. Crea un nuovo progetto ESP-IDF
2. Copia il codice nei rispettivi file
3. Configura il progetto: `idf.py menuconfig`
4. Compila: `idf.py build`
5. Flasha: `idf.py -p [PORTA] flash monitor`

L'output sulla console mostrerà i valori della sequenza di Fibonacci calcolati dal modulo WASM.

Alcuni punti importanti da notare:
- Usiamo uno stack di 32KB per il task WASM (`32768` bytes)
- Il runtime WASM usa 1KB di stack (`1024` bytes)
- Abbiamo implementato una funzione nativa `print` che può essere chiamata dal codice WASM
- Il modulo viene eseguito in un task FreeRTOS dedicato

Vuoi che ti mostri come aggiungere altre funzioni native o come modificare l'esempio per un caso d'uso specifico?