#include "driver/uart.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "he_settings.h"
#include "string.h"  // per memset()
#include <stdio.h>
#include <string.h>
#include <stdarg.h>

#include "esp_log.h"
#include "esp_system.h"
#include "esp_heap_caps.h"  // per le funzioni di heap debugging
#include "sdkconfig.h"

#include "he_defines.h"
#include "he_monitor.h"
#include "he_device.h"

#include <stdio.h>
#include <string.h>
#include <stdarg.h>

#include "he_defines.h"



////////////////////////////////////////////////////////////////

void enable_log_debug(){
    esp_log_level_set("*", ESP_LOG_DEBUG); 
    //esp_log_level_set("*", ESP_LOG_VERBOSE);
}

void monitor_disable(){
    settings_t* settings = get_main_settings();
    settings->_disable_monitor = true;
    enable_log_debug(); // ??
}

void monitor_enable(){
    settings_t* settings = get_main_settings();
    settings->_disable_monitor = false;
    enable_log_debug();
}

////////////////////////////////////////////////////////////////

// Funzione proxy per i log del monitor
void monitor_printf(const char* format, ...) {
    #if SERIAL_WRITER_BROKER_ENABLE

    va_list args;
    va_list args_copy;
    
    // Prima chiamata per determinare la lunghezza necessaria
    va_start(args, format);
    va_copy(args_copy, args);
    int required_length = vsnprintf(NULL, 0, format, args) + 1; // +1 per il terminatore
    va_end(args);
    
    // Allocazione della memoria
    char* buffer = (char*)malloc(required_length);
    if (buffer == NULL) {
        return;
    }
    
    // Seconda chiamata per effettuare la formattazione
    vsnprintf(buffer, required_length, format, args_copy);
    va_end(args_copy);

    size_t tot_len = (required_length + strlen(MONITOR_START) + strlen(MONITOR_END)+1);
    char* buffer2Print = (char*)malloc(tot_len*sizeof(char));
    sprintf(buffer2Print, "%s%s%s", MONITOR_START, buffer, MONITOR_END);
    free(buffer);

    safe_printf(buffer2Print);

    free(buffer2Print);

    #else
    settings_t* settings = get_main_settings();
    if(settings->_exclusive_serial_mode || settings->_disable_monitor) return;

    if(settings->_serial_mutex && xSemaphoreTake(settings->_serial_mutex, pdMS_TO_TICKS(SERIAL_SEMAPHORE_WAIT_MS)) != pdTRUE) {
        return; // Skip printing if can't get mutex
    }

    printf(MONITOR_START);
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    printf(MONITOR_END);
    
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);    
    if(settings->_serial_mutex) xSemaphoreGive(settings->_serial_mutex);
    //vTaskDelay(pdMS_TO_TICKS(10)); // 0.01s delay after printing
    #endif
}

////////////////////////////////////////////////////////////////

// La nostra task di monitoraggio
void taskStatusMonitor(void *pvParameters) {
    TaskStatus_t *pxTaskStatusArray;
    volatile UBaseType_t uxArraySize;
    uint32_t ulTotalRunTime, ulStatsAsPercentage;
    char pcWriteBuffer[50];

    settings_t* settings = get_main_settings();
    
    while(1) {
        if(settings->_exclusive_serial_mode || settings->_disable_monitor) {
            goto end;
        }

        monitor_printf("!!clear!!");
        uxArraySize = uxTaskGetNumberOfTasks();
        pxTaskStatusArray = pvPortMalloc(uxArraySize * sizeof(TaskStatus_t));
        
        if (pxTaskStatusArray != NULL) {
            uxArraySize = uxTaskGetSystemState(pxTaskStatusArray, uxArraySize, &ulTotalRunTime);
            
            multi_heap_info_t ram_info = get_ram_info();

            monitor_printf("\n=== System Task Status (%d tasks) ===\n", uxArraySize);
            monitor_printf("Total Runtime: %u ticks\n", ulTotalRunTime);
            monitor_printf("Free Heap: %u bytes\n", esp_get_free_heap_size());
            monitor_printf("Min Free Heap: %u bytes\n", esp_get_minimum_free_heap_size());
            
            for(int i = 0; i < uxArraySize; i++) {
                if(settings->_exclusive_serial_mode || settings->_disable_monitor) {
                    goto end;
                }

                TaskStatus_t status = pxTaskStatusArray[i];

                // Calculate CPU usage percentage
                if(ulTotalRunTime > 0) {
                    ulStatsAsPercentage = (status.ulRunTimeCounter * 100UL) / ulTotalRunTime;
                } else {
                    ulStatsAsPercentage = 0;
                }

                const char *taskState = 
                    status.eCurrentState == eRunning  ? "Running" :
                    status.eCurrentState == eReady    ? "Ready" :
                    status.eCurrentState == eBlocked  ? "Blocked" :
                    status.eCurrentState == eSuspended? "Suspended" :
                    status.eCurrentState == eDeleted  ? "Deleted" : "Unknown";

                monitor_printf("\nTask: %s", status.pcTaskName);
                monitor_printf("- CPU: %u%%", ulStatsAsPercentage);
                monitor_printf("- Priority: %d (Base: %d)", 
                    status.uxCurrentPriority,
                    status.uxBasePriority);
                monitor_printf("- Stack HWM: %u bytes (%u%%)", 
                    status.usStackHighWaterMark * sizeof(StackType_t),
                    (status.usStackHighWaterMark * 100) / ram_info.total_allocated_bytes);
                monitor_printf("- State: %s", taskState);
                monitor_printf("- Core: %d", status.xCoreID);
                
                /*if(status.eCurrentState == eBlocked) {
                    vTaskGetTaskInfo(status.xHandle, NULL, pdTRUE, pcWriteBuffer); // vTaskGetTaskInfo doesn't exists
                    monitor_printf("- Block Time: %s", pcWriteBuffer);
                }*/
            }
            
            vPortFree(pxTaskStatusArray);
        } else {
            monitor_printf("Failed to allocate memory for monitoring");
        }
        
        end:
        monitor_printf("!!end!!");
        vTaskDelay(pdMS_TO_TICKS(1000*MONITOR_EVERY_SECONDS));
    }
}

void init_tasksMonitor(void) {
    #if configUSE_TRACE_FACILITY != 1
    #error "configUSE_TRACE_FACILITY must be 1 in FreeRTOSConfig.h"
    #endif
    
    #if configGENERATE_RUN_TIME_STATS != 1
    #error "configGENERATE_RUN_TIME_STATS must be 1 in FreeRTOSConfig.h"
    #endif

    // Crea la task di monitoraggio con priorità più bassa
    xTaskCreate(taskStatusMonitor, "TaskMonitor", 4096, NULL, 0, NULL);
    
    ESP_LOGI(TAG, "Task monitor initialized");
}
