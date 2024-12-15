#pragma once

#define SERIAL_TASK_ADV 1
#define WASM_TASK_ADV 1

#define WASM_TASK_CORE 1
#define SERIAL_TASK_CORE 0

#define ENABLE_WATCHDOG 1

#if ENABLE_WATCHDOG
#define WATCHDOG_RESET  esp_task_wdt_reset();
#define WATCHDOG_ADD    esp_task_wdt_add(NULL); WATCHDOG_RESET
#define WATCHDOG_END    WATCHDOG_RESET vTaskDelay(pdMS_TO_TICKS(10)); esp_task_wdt_delete(NULL);
#else 
#define WATCHDOG_RESET
#define WATCHDOG_ADD
#define WATCHDOG_END
#endif
