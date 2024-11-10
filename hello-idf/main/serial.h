#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#define BUF_SIZE 1024
#define COMMAND_PREFIX "$$$WRITE_FILE"
#define STACK_SIZE (8192)  // Aumentato a 8KB

// Task per gestire l'input seriale
void serial_handler_task(void *pvParameters) {
    // Alloca i buffer sullo heap invece che sullo stack
    char *command = malloc(BUF_SIZE);
    char *filename = malloc(256);
    char *buf = malloc(BUF_SIZE);
    
    if (!command || !filename || !buf) {
        ESP_LOGE(TAG, "Failed to allocate buffers");
        goto cleanup;
    }

    ESP_LOGI(TAG, "Serial handler started");
    
    while(1) {
        // Controlla lo stack rimanente
        if (uxTaskGetStackHighWaterMark(NULL) < 512) {
            ESP_LOGW(TAG, "Stack getting low! %d bytes remaining", 
                    uxTaskGetStackHighWaterMark(NULL));
        }
        
        if(fgets(command, BUF_SIZE, stdin) != NULL) {
            // Rimuove il newline finale
            command[strcspn(command, "\n")] = 0;
            
            // Verifica se è il comando di scrittura file
            if(strncmp(command, COMMAND_PREFIX, strlen(COMMAND_PREFIX)) == 0) {
                size_t filesize;
                if(sscanf(command + strlen(COMMAND_PREFIX) + 1, "%[^,],%zu", 
                         filename, &filesize) == 2) {
                    
                    ESP_LOGI(TAG, "Richiesta scrittura file: %s (%zu bytes)", 
                            filename, filesize);
                    
                    FILE* f = fopen(filename, "w");
                    if(f == NULL) {
                        printf("ERROR: Cannot open file\n");
                        continue;
                    }
                    
                    // Legge e scrive il file
                    size_t remaining = filesize;
                    
                    while(remaining > 0) {
                        size_t to_read = (remaining > BUF_SIZE) ? BUF_SIZE : remaining;
                        size_t received = fread(buf, 1, to_read, stdin);
                        
                        if(received > 0) {
                            fwrite(buf, 1, received, f);
                            remaining -= received;
                        } else {
                            break;
                        }
                    }
                    
                    fclose(f);
                    printf("OK: File written successfully\n");
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

cleanup:
    free(command);
    free(filename);
    free(buf);
    vTaskDelete(NULL);
}

// Funzione per avviare il task
esp_err_t start_serial_handler(void) {
    BaseType_t ret = xTaskCreatePinnedToCore(
        serial_handler_task,
        "serial_handler",
        STACK_SIZE,     // Aumentato a 8KB
        NULL,
        5,              // Priorità media
        NULL,           // Non ci serve l'handle
        1               // Core 1
    );
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create serial handler task");
        return ESP_FAIL;
    }
    
    return ESP_OK;
}