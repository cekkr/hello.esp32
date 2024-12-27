#pragma once

#ifndef HE_DEFINES_H
#define HE_DEFINES_H


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
#include "esp_log.h"

// Watchdog
#include "esp_task_wdt.h"
#include "rtc_wdt.h"

#include <stdbool.h>

////////////////////////////////////////////////////////////////

// Essential constants
static const char *TAG = "HELLOESP";
#define SD_MOUNT_POINT "/sdcard"
#define MAX_FILENAME 256

#define PAGING_PATH SD_MOUNT_POINT "/pages"

////////////////////////////////////////////////////////////////

#define SERIAL_TASK_ADV 1
#define SERIAL_TASK_CORE 0
#define SERIAL_TASK_PRIORITY 5

////////////////////////////////////////////////////////////////
/////////////////////// TASK BROKER ////////////////////////////
////////////////////////////////////////////////////////////////

#define MAX_TASKS 8
#define MAX_TASK_NAME_LENGTH 32
#define MAX_MESSAGE_SIZE LOG_BUFFER_SIZE
#define BROKER_QUEUE_SIZE 8
#define BROKER_TASK_PRIORITY 20
#define BROKER_TASK_STACK_SIZE (1024*32)
#define BROKER_TASK_CORE 1

////////////////////////////////////////////////////////////////
///////////// SERIAL_WRITER_BROKER /////////////////////////////
////////////////////////////////////////////////////////////////

#define SERIAL_WRITER_WAIT_MS 10

#define LOG_BUFFER_SIZE 2048

#define SERIAL_WRITER_BROKER_ENABLE 1
#define SERIAL_WRITER_BROKER_TASK_CORE BROKER_TASK_CORE
#define SERIAL_WRITER_BROKER_TASK_PRIORITY BROKER_TASK_PRIORITY
#define SERIAL_WRITER_BROKER_TASK_STACK_SIZE (4*1024)

#if SERIAL_WRITER_BROKER_ENABLE
static const char serial_writer_broker_name[] = "serial_writer_broker";
static const char serial_writer_sender_name[] = "serial_writer_sender";
#endif

void serial_write(const char* data, size_t len);
void* serial_print(const char* msg);

////////////////////////////////////////////////////////////////
///////////////////////// WASM 3 ///////////////////////////////
////////////////////////////////////////////////////////////////

#define WASM_TASK_ADV 1
#define WASM_TASK_CORE 0

#define WASM_STACK_SIZE (32*1024)  
#define WASM_TASK_SIZE (32*1024)
#define WASM_TASK_PRIORITY 5

#define WASM_PTRS_64BITS 0

////////////////////////////////////////////////////////////////
//////////////////////// WATCHDOG //////////////////////////////
////////////////////////////////////////////////////////////////

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

///
/// WASM3
///
#define ENABLE_WATCHDOG_WASM3 0

///
/// Serial and UART
///

////////////////////////////////////////////////////////////////////////
// or Component config -> Driver configurations -> SPI configuration -> (x) Place SPI driver ISR function into IRAM   
#define ENABLE_INTR_FLAG_IRAM_SPI 1 // for SPI interrupts
#define ENABLE_SPIRAM 0

//#define SERIAL_BAUD 115200
#define SERIAL_BAUD 230400

#define SERIAL_SEMAPHORE_WAIT_MS 25
#define SERIAL_MUTEX_MAX_TRIES 10

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
/// Serial and commands
///

#define MAX_CMD_LENGTH 512
#define SERIAL_STACK_SIZE (1024*16)

#define EXCLUSIVE_SERIAL_ON_CMD false

///
/// Serial semaphore
///

#define ENABLE_MONITOR 1
#define MONITOR_EVERY_SECONDS 4

void safe_printf(const char* format, ...);

#define LOG_COLOR_BLACK   "30"
#define LOG_COLOR_RED     "31"
#define LOG_COLOR_GREEN   "32" 
#define LOG_COLOR_BROWN   "33"
#define LOG_COLOR_BLUE    "34"
#define LOG_COLOR_PURPLE  "35"
#define LOG_COLOR_CYAN    "36"
#define LOG_COLOR_RESET   "\033[0m"
#define LOG_COLOR(COLOR)  "\033[0;" COLOR "m"

#define ESP_LOGD(tag, format, ...) do { \
   char* log_buf = malloc(LOG_BUFFER_SIZE*sizeof(char)); \
   size_t len = snprintf(log_buf, LOG_BUFFER_SIZE, LOG_COLOR(LOG_COLOR_CYAN) "D (%s) %s: " format LOG_COLOR_RESET "\n", esp_log_system_timestamp(), tag, ##__VA_ARGS__); \
   safe_printf("%s", log_buf); \
   free(log_buf); \
} while(0)

#define ESP_LOGI(tag, format, ...) do { \
   char* log_buf = malloc(LOG_BUFFER_SIZE*sizeof(char)); \
   size_t len = snprintf(log_buf, LOG_BUFFER_SIZE, LOG_COLOR(LOG_COLOR_GREEN) "I (%s) %s: " format LOG_COLOR_RESET "\n", esp_log_system_timestamp(), tag, ##__VA_ARGS__); \
   safe_printf("%s", log_buf); \
   free(log_buf); \
} while(0)

#define ESP_LOGW(tag, format, ...) do { \
   char* log_buf = malloc(LOG_BUFFER_SIZE*sizeof(char)); \
   size_t len = snprintf(log_buf, LOG_BUFFER_SIZE, LOG_COLOR(LOG_COLOR_BROWN) "W (%s) %s: " format LOG_COLOR_RESET "\n", esp_log_system_timestamp(), tag, ##__VA_ARGS__); \
   safe_printf("%s", log_buf); \
   free(log_buf); \
} while(0)

#define ESP_LOGE(tag, format, ...) do { \
   char* log_buf = malloc(LOG_BUFFER_SIZE*sizeof(char)); \
   size_t len = snprintf(log_buf, LOG_BUFFER_SIZE, LOG_COLOR(LOG_COLOR_RED) "E (%s) %s: " format LOG_COLOR_RESET "\n", esp_log_system_timestamp(), tag, ##__VA_ARGS__); \
   safe_printf("%s", log_buf); \
   free(log_buf); \
} while(0)

////////////////////////////////////////////////////////////////

#define MIN(x, y) ((x) < (y) ? (x) : (y)) 

#endif