#pragma once

#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include "driver/gpio.h"
#include "driver/spi_common.h"
#include "driver/uart_vfs.h"
#include "hal/uart_ll.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_trace.h"

// Watchdog
#include "esp_task_wdt.h"
#include "rtc_wdt.h"

#include <stdbool.h>

////////////////////////////////////////////////////////////////

// Essential constants
static const char *TAG = "HELLOESP";
#define SD_MOUNT_POINT "/sdcard"
#define MAX_FILENAME 256

////////////////////////////////////////////////////////////////

#define SERIAL_TASK_ADV 1
#define SERIAL_TASK_CORE 0

// WASM 3
#define WASM_TASK_ADV 1
#define WASM_TASK_CORE 1

#define WASM_TASK_SIZE (64*1024)
#define WASM_STACK_SIZE (64*1024)  
#define WASM_TASK_PRIORITY 5

////////////////////////////////////////////////////////////////////////
#define ENABLE_WATCHDOG 0

#if ENABLE_WATCHDOG
#define WATCHDOG_RESET  esp_task_wdt_reset();
#define WATCHDOG_ADD    esp_task_wdt_add(NULL); WATCHDOG_RESET
#define WATCHDOG_END    WATCHDOG_RESET vTaskDelay(pdMS_TO_TICKS(10)); esp_task_wdt_delete(NULL);
#else 
#define WATCHDOG_RESET reset_wdt();
#define WATCHDOG_ADD reset_wdt();
#define WATCHDOG_END
#endif

/// WASM3
#define ENABLE_WATCHDOG_WASM3 0

////////////////////////////////////////////////////////////////////////
// or Component config -> Driver configurations -> SPI configuration -> (x) Place SPI driver ISR function into IRAM   
#define ENABLE_INTR_FLAG_IRAM_SPI 0 // for SPI interrupts
#define ENABLE_SPIRAM 0
#define ENABLE_MONITOR 0

//#define SERIAL_BAUD 115200
#define SERIAL_BAUD 230400

///
/// SD and touch
///
#define SD_SCK  18
#define SD_MISO 19
#define SD_MOSI 23
#define SD_CS   5

#define SPI_DMA_CHAN    1

#define CONFIG_XPT2046_ENABLE_DIFF_BUS 1

///
/// Global vars
///

static bool exclusive_serial_mode = false;
static bool disable_monitor = false;