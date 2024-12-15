#pragma once

#define SERIAL_TASK_ADV 1
#define WASM_TASK_ADV 1

#define TASK_CORE 0

#define ENABLE_WATCHDOG 1

#if ENABLE_WATCHDOG
#define WATCHDOG_RESET esp_task_wdt_reset();
#else 
#define WATCHDOG_RESET
#endif
