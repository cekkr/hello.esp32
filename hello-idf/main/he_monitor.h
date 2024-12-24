#pragma once

#include "sdkconfig.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "string.h"  // per memset()
#include "esp_heap_caps.h"  // per le funzioni di heap debugging

#include <stdio.h>
#include <string.h>
#include <stdarg.h>

#include "he_defines.h"

////////////////////////////////////////////////////////////////

// Codici per formattare l'output
/*#define MONITOR_START "!!TASKMONITOR!!\033[34m[TASK MONITOR]\033[0m "  // Blu
#define MONITOR_SEPARATOR "\033[36m"                    // Ciano
#define MONITOR_WARNING "\033[33m"                      // Giallo
#define MONITOR_CRITICAL "\033[31m"                     // Rosso
#define MONITOR_RESET "\033[0m!!TASKMONITOREND!!\n"                         // Reset colore*/

#define MONITOR_START "!!TASKMONITOR!!"
#define MONITOR_END "!!TASKMONITOREND!!\n" 

////////////////////////////////////////////////////////////////

void enable_log_debug();

void monitor_disable();

void monitor_enable();

////////////////////////////////////////////////////////////////

// Funzione proxy per i log del monitor
void monitor_printf(const char* format, ...);

////////////////////////////////////////////////////////////////

// La nostra task di monitoraggio
void taskStatusMonitor(void *pvParameters);

void init_tasksMonitor(void);

////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////

typedef enum {
    STACK_USAGE_NORMAL = 0,
    STACK_USAGE_WARNING,
    STACK_USAGE_CRITICAL
} stack_usage_level_t;

typedef struct {
    TaskHandle_t task;
    size_t warning_threshold;   // es: 75% dello stack usato
    size_t critical_threshold;  // es: 90% dello stack usato
} stack_monitor_config_t;
