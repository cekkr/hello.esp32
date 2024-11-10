#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "sdmmc_cmd.h"
#include "esp_vfs_fat.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// Definizione delle costanti per il thread
#define SERIAL_TASK_PRIORITY     5
#define SERIAL_TASK_STACK_SIZE   8192  // 8KB di stack
#define SERIAL_TASK_CORE_ID      1     // Esegue sul core 1


#define UART_NUM UART_NUM_0
#define BUF_SIZE 1024
#define COMMAND_PREFIX "$$$WRITE_FILE"

// Struttura per memorizzare i dettagli del file
typedef struct {
    char filename[256];
    size_t filesize;
} file_info_t;

// Funzione per parsare il comando ricevuto
bool parse_command(const char* command, file_info_t* file_info) {
    char filename[256];
    size_t filesize;
    
    if (strncmp(command, COMMAND_PREFIX, strlen(COMMAND_PREFIX)) != 0) {
        return false;
    }
    
    // Formato atteso: $$$WRITE_FILE,filename.txt,1234
    if (sscanf(command + strlen(COMMAND_PREFIX) + 1, "%[^,],%zu", 
               filename, &filesize) != 2) {
        return false;
    }
    
    strncpy(file_info->filename, filename, sizeof(file_info->filename) - 1);
    file_info->filesize = filesize;
    return true;
}

// Funzione principale per la gestione della scrittura file
void handle_serial_file_write(void) {
    uint8_t* data = (uint8_t*) malloc(BUF_SIZE);
    char* command = (char*) malloc(BUF_SIZE);
    size_t command_len = 0;
    file_info_t file_info;
    
    // Configurazione UART
    uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE
    };
    uart_param_config(UART_NUM, &uart_config);
    uart_driver_install(UART_NUM, BUF_SIZE * 2, BUF_SIZE * 2, 0, NULL, 0);
    
    while (1) {
        // Legge dalla seriale fino a trovare un newline
        uint8_t c;
        int len = uart_read_bytes(UART_NUM, &c, 1, portMAX_DELAY);
        if (len > 0) {
            if (c == '\n') {
                command[command_len] = '\0';
                
                // Verifica se è un comando valido
                if (parse_command(command, &file_info)) {
                    ESP_LOGI(TAG, "Comando ricevuto per file: %s, size: %zu", 
                            file_info.filename, file_info.filesize);
                    
                    // Prepara il percorso completo del file
                    char filepath[512];
                    snprintf(filepath, sizeof(filepath), "%s/%s", 
                            SD_MOUNT_POINT, file_info.filename);
                    
                    // Apre il file in scrittura
                    FILE* f = fopen(filepath, "w");
                    if (f == NULL) {
                        ESP_LOGE(TAG, "Impossibile aprire il file");
                        uart_write_bytes(UART_NUM, "ERROR: Cannot open file\n", 22);
                        command_len = 0;
                        continue;
                    }
                    
                    // Legge e scrive i dati
                    size_t remaining = file_info.filesize;
                    while (remaining > 0) {
                        size_t to_read = (remaining > BUF_SIZE) ? BUF_SIZE : remaining;
                        int received = uart_read_bytes(UART_NUM, data, to_read, pdMS_TO_TICKS(1000));
                        
                        if (received > 0) {
                            fwrite(data, 1, received, f);
                            remaining -= received;
                        } else {
                            ESP_LOGE(TAG, "Timeout nella ricezione dati");
                            break;
                        }
                    }
                    
                    fclose(f);
                    
                    // Invia conferma
                    if (remaining == 0) {
                        uart_write_bytes(UART_NUM, "OK: File written successfully\n", 28);
                    } else {
                        uart_write_bytes(UART_NUM, "ERROR: File write incomplete\n", 27);
                    }
                }
                command_len = 0;
            } else if (command_len < BUF_SIZE - 1) {
                command[command_len++] = c;
            }
        }
    }
    
    free(data);
    free(command);
}

///
/// Task management
///


// Handle del task
TaskHandle_t serial_task_handle = NULL;

// Wrapper function per il task
void serial_task(void *pvParameters) {
    ESP_LOGI("SERIAL_TASK", "Starting serial file writer task");
    
    // Chiama la funzione di gestione seriale
    handle_serial_file_write();
    
    // Non dovremmo mai arrivare qui dato che handle_serial_file_write ha un loop infinito
    vTaskDelete(NULL);
}

// Funzione per avviare il thread
esp_err_t start_serial_file_writer(void) {
    esp_err_t ret = ESP_OK;
    
    // Crea il task
    BaseType_t xReturned = xTaskCreatePinnedToCore(
        serial_task,                // Funzione del task
        "serial_file_writer",       // Nome del task (per debug)
        SERIAL_TASK_STACK_SIZE,     // Stack size
        NULL,                       // Parametri (non ne usiamo)
        SERIAL_TASK_PRIORITY,       // Priorità
        &serial_task_handle,        // Handle del task
        SERIAL_TASK_CORE_ID         // Core su cui eseguire il task
    );
    
    if (xReturned != pdPASS) {
        ESP_LOGE("SERIAL_TASK", "Failed to create task");
        ret = ESP_FAIL;
    }
    
    return ret;
}

// Funzione per fermare il thread (opzionale)
void stop_serial_file_writer(void) {
    if (serial_task_handle != NULL) {
        vTaskDelete(serial_task_handle);
        serial_task_handle = NULL;
    }
}