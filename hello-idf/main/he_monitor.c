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

#include "he_monitor.h"


////////////////////////////////////////////////////////////////

void enable_log_debug(){
    esp_log_level_set("*", ESP_LOG_DEBUG); 
    //esp_log_level_set("*", ESP_LOG_VERBOSE);
}

void monitor_disable(){
    disable_monitor = true;
    enable_log_debug();
}

void monitor_enable(){
    disable_monitor = true;
    enable_log_debug();
}

////////////////////////////////////////////////////////////////

// Funzione proxy per i log del monitor
void monitor_printf(const char* format, ...) {
    if(exclusive_serial_mode || disable_monitor) return;

    if(serial_mutex && xSemaphoreTake(serial_mutex, pdMS_TO_TICKS(SERIAL_SEMAPHORE_WAIT_MS)) != pdTRUE) {
        return; // Skip printing if can't get mutex
    }

    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
    
    printf(MONITOR_START);
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    printf(MONITOR_END);
    
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
    
    if(serial_mutex) xSemaphoreGive(serial_mutex);
    //vTaskDelay(pdMS_TO_TICKS(10)); // 0.01s delay after printing
}

////////////////////////////////////////////////////////////////

// La nostra task di monitoraggio
void taskStatusMonitor(void *pvParameters) {
    TaskStatus_t *pxTaskStatusArray;
    volatile UBaseType_t uxArraySize;
    uint32_t ulTotalRunTime, ulStatsAsPercentage;
    char pcWriteBuffer[50];
    
    while(1) {
        if(exclusive_serial_mode || disable_monitor) {
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        monitor_printf("!!clear!!");
        uxArraySize = uxTaskGetNumberOfTasks();
        pxTaskStatusArray = pvPortMalloc(uxArraySize * sizeof(TaskStatus_t));
        
        if (pxTaskStatusArray != NULL) {
            uxArraySize = uxTaskGetSystemState(pxTaskStatusArray, uxArraySize, &ulTotalRunTime);
            
            monitor_printf("\n=== System Task Status (%d tasks) ===\n", uxArraySize);
            monitor_printf("Total Runtime: %u ticks\n", ulTotalRunTime);
            monitor_printf("Free Heap: %u bytes\n", esp_get_free_heap_size());
            monitor_printf("Min Free Heap: %u bytes\n", esp_get_minimum_free_heap_size());
            
            for(int i = 0; i < uxArraySize; i++) {
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
                    (status.usStackHighWaterMark * 100) / configMINIMAL_STACK_SIZE);
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
