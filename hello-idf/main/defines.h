#pragma once

#define SERIAL_TASK_ADV 1
#define WASM_TASK_CORE 0

// WASM 3
#define WASM_TASK_ADV 1
#define SERIAL_TASK_CORE 0

#define WASM_STACK_SIZE (64*1024)  // Esempio di dimensione stack
#define WASM_TASK_PRIORITY 5

////////////////////////////////////////////////////////////////////////
#define ENABLE_WATCHDOG 1

#if ENABLE_WATCHDOG
#define WATCHDOG_RESET  esp_task_wdt_reset();
#define WATCHDOG_ADD    esp_task_wdt_add(NULL); WATCHDOG_RESET
#define WATCHDOG_END    WATCHDOG_RESET vTaskDelay(pdMS_TO_TICKS(10)); esp_task_wdt_delete(NULL);
#else 
#define WATCHDOG_RESET reset_wdt();
#define WATCHDOG_ADD reset_wdt();
#define WATCHDOG_END
#endif

////////////////////////////////////////////////////////////////////////
// or Component config -> Driver configurations -> SPI configuration -> (x) Place SPI driver ISR function into IRAM   
#define ENABLE_INTR_FLAG_IRAM_SPI 0 // for SPI interrupts

#define ENABLE_SPIRAM 0

///
/// Global vars
///

static bool exclusive_serial_mode = false;
static bool disable_monitor = false;