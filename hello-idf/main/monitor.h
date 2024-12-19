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

#include "defines.h"

////////////////////////////////////////////////////////////////

// Codici per formattare l'output
#define MONITOR_START "!!TASKMONITOR!!\033[34m[TASK MONITOR]\033[0m "  // Blu
#define MONITOR_SEPARATOR "\033[36m"                    // Ciano
#define MONITOR_WARNING "\033[33m"                      // Giallo
#define MONITOR_CRITICAL "\033[31m"                     // Rosso
#define MONITOR_RESET "\033[0m!!TASKMONITOREND!!"                         // Reset colore

// Funzione proxy per i log del monitor
void monitor_printf(const char* format, ...) {
    if(exclusive_serial_mode) return;

    printf(MONITOR_START);
    // example printf(MONITOR_START MONITOR_WARNING);
    
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    
    printf(MONITOR_RESET);
}

////////////////////////////////////////////////////////////////

// La nostra task di monitoraggio
void taskStatusMonitor(void *pvParameters) {
    TaskStatus_t *pxTaskStatusArray;
    volatile UBaseType_t uxArraySize;
    uint32_t ulTotalRunTime;
    
    while(1) {
        // Ottiene il numero di task nel sistema
        uxArraySize = uxTaskGetNumberOfTasks();
        ESP_LOGI(TAG, "Numero di task attive: %d", uxArraySize);
        
        // Alloca memoria per l'array di status
        pxTaskStatusArray = pvPortMalloc(uxArraySize * sizeof(TaskStatus_t));
        
        if (pxTaskStatusArray != NULL) {
            // Ottiene lo stato di tutte le task
            uxArraySize = uxTaskGetSystemState(pxTaskStatusArray, 
                                             uxArraySize, 
                                             &ulTotalRunTime);
            
            // Stampa informazioni per ogni task
            monitor_printf("\n=== Status Task del Sistema ===\n");
            for(int i = 0; i < uxArraySize; i++) {
                monitor_printf("\nTask: %s\n", pxTaskStatusArray[i].pcTaskName);
                monitor_printf("- Priorità: %d\n", pxTaskStatusArray[i].uxCurrentPriority);
                monitor_printf("- Stack High Water Mark: %d bytes\n", 
                       pxTaskStatusArray[i].usStackHighWaterMark * sizeof(StackType_t));
                
                // Converti lo stato numerico in stringa
                char *taskState;
                switch(pxTaskStatusArray[i].eCurrentState) {
                    case eRunning: taskState = "In esecuzione"; break;
                    case eReady: taskState = "Pronta"; break;
                    case eBlocked: taskState = "Bloccata"; break;
                    case eSuspended: taskState = "Sospesa"; break;
                    case eDeleted: taskState = "Eliminata"; break;
                    default: taskState = "Sconosciuto"; break;
                }
                monitor_printf("- Stato: %s\n", taskState);
            }
            monitor_printf("===========================\n");
            
            // Libera la memoria
            vPortFree(pxTaskStatusArray);
        } else {
            monitor_printf("Impossibile allocare memoria per il monitoraggio");
        }
        
        // Aspetta 10 secondi prima del prossimo controllo
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void init_tasksMonitor(void) {
    // Crea la task di monitoraggio con priorità più bassa
    xTaskCreate(taskStatusMonitor, "TaskMonitor", 4096, NULL, 0, NULL);
    
    ESP_LOGI(TAG, "Task monitor initialized");
}

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

void advancedStackMonitor(void *pvParameters) {
    stack_monitor_config_t *config = (stack_monitor_config_t *)pvParameters;
    UBaseType_t stackHighWaterMark;
    size_t stackSize = uxTaskGetStackSize(config->task);
    stack_usage_level_t lastLevel = STACK_USAGE_NORMAL;
    
    while(1) {
        stackHighWaterMark = uxTaskGetStackHighWaterMark(config->task);
        size_t usedStack = stackSize - (stackHighWaterMark * sizeof(StackType_t));
        float usagePercentage = ((float)usedStack / stackSize) * 100;
        
        // Determina il livello di utilizzo
        stack_usage_level_t currentLevel;
        if (usagePercentage >= config->critical_threshold) {
            currentLevel = STACK_USAGE_CRITICAL;
        } else if (usagePercentage >= config->warning_threshold) {
            currentLevel = STACK_USAGE_WARNING;
        } else {
            currentLevel = STACK_USAGE_NORMAL;
        }
        
        // Log solo se il livello è cambiato
        if (currentLevel != lastLevel) {
            const char *taskName = pcTaskGetName(config->task);
            
            switch(currentLevel) {
                case STACK_USAGE_CRITICAL:
                    monitor_printf( "CRITICO: Task %s usa %.1f%% dello stack!", 
                            taskName, usagePercentage);
                    // Qui potresti aggiungere azioni di emergenza
                    break;
                    
                case STACK_USAGE_WARNING:
                    monitor_printf( "ATTENZIONE: Task %s usa %.1f%% dello stack", 
                            taskName, usagePercentage);
                    break;
                    
                case STACK_USAGE_NORMAL:
                    monitor_printf( "Task %s tornata a utilizzo normale: %.1f%%", 
                            taskName, usagePercentage);
                    break;
            }
            
            lastLevel = currentLevel;
        }
        
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void void_task(){}

void example_task_monitor(){
    TaskHandle_t taskToMonitor;
    
    // Crea la task da monitorare
    xTaskCreate(void_task, "MyTask", 4096, NULL, 5, &taskToMonitor);
    
    // Configura il monitoraggio
    stack_monitor_config_t config = {
        .task = taskToMonitor,
        .warning_threshold = 75,  // 75%
        .critical_threshold = 90  // 90%
    };
    
    // Crea la task di monitoraggio
    xTaskCreate(advancedStackMonitor, "StackMonitor", 2048, &config, 1, NULL);
}