#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

// Definizioni
#define BUF_SIZE 1024
#define MAX_FILENAME 256
#define STACK_SIZE (8192)

// Comandi
#define CMD_WRITE_FILE "$$$WRITE_FILE$$$"
#define CMD_READ_FILE  "$$$READ_FILE$$$"
#define CMD_LIST_FILES "$$$LIST_FILES$$$"
#define CMD_DELETE_FILE "$$$DELETE_FILE$$$"

// Codici di risposta
typedef enum {
    STATUS_OK = 0,
    STATUS_ERROR_OPEN,
    STATUS_ERROR_WRITE,
    STATUS_ERROR_READ,
    STATUS_ERROR_MEMORY,
    STATUS_ERROR_PARAMS,
    STATUS_ERROR_NOT_FOUND
} command_status_t;

// Struttura per i parametri del comando
typedef struct {
    char filename[MAX_FILENAME];
    size_t filesize;
} command_params_t;

// Funzione per inviare la risposta
static void send_response(command_status_t status, const char* message) {
    switch(status) {
        case STATUS_OK:
            printf("OK: %s\n", message);
            break;
        default:
            printf("ERROR: %s\n", message);
            break;
    }
}

// Funzione per il parsing dei comandi
static command_status_t parse_command(const char* command, char* cmd_type, command_params_t* params) {
    if (strncmp(command, CMD_WRITE_FILE, strlen(CMD_WRITE_FILE)) == 0) {
        strcpy(cmd_type, CMD_WRITE_FILE);
        if (sscanf(command + strlen(CMD_WRITE_FILE) + 1, "%[^,],%zu",
                   params->filename, &params->filesize) != 2) {
            return STATUS_ERROR_PARAMS;
        }
    } else if (strncmp(command, CMD_READ_FILE, strlen(CMD_READ_FILE)) == 0) {
        strcpy(cmd_type, CMD_READ_FILE);
        if (sscanf(command + strlen(CMD_READ_FILE) + 1, "%s",
                   params->filename) != 1) {
            return STATUS_ERROR_PARAMS;
        }
    }
    // ... altri comandi ...
    return STATUS_OK;
}

// Funzione per la scrittura del file
static command_status_t handle_write_file(const command_params_t* params) {
    FILE* f = fopen(params->filename, "w");
    if (f == NULL) {
        return STATUS_ERROR_OPEN;
    }

    char* buf = malloc(BUF_SIZE);
    if (!buf) {
        fclose(f);
        return STATUS_ERROR_MEMORY;
    }

    size_t remaining = params->filesize;
    command_status_t status = STATUS_OK;

    while (remaining > 0) {
        size_t to_read = (remaining > BUF_SIZE) ? BUF_SIZE : remaining;
        size_t received = fread(buf, 1, to_read, stdin);

        if (received > 0) {
            if (fwrite(buf, 1, received, f) != received) {
                status = STATUS_ERROR_WRITE;
                break;
            }
            remaining -= received;
        } else {
            status = STATUS_ERROR_READ;
            break;
        }
    }

    free(buf);
    fclose(f);
    return status;
}

// Task principale per la gestione seriale
void serial_handler_task(void *pvParameters) {
    char* command = malloc(BUF_SIZE);
    char* cmd_type = malloc(BUF_SIZE);
    command_params_t* params = malloc(sizeof(command_params_t));

    if (!command || !cmd_type || !params) {
        ESP_LOGE(TAG, "Failed to allocate buffers");
        goto cleanup;
    }

    ESP_LOGI(TAG, "Serial handler started");

    while(1) {
        // Controllo stack
        if (uxTaskGetStackHighWaterMark(NULL) < 512) {
            ESP_LOGW(TAG, "Stack getting low! %d bytes remaining",
                     uxTaskGetStackHighWaterMark(NULL));
        }

        if (fgets(command, BUF_SIZE, stdin) != NULL) {
            command[strcspn(command, "\n")] = 0;
            
            command_status_t parse_status = parse_command(command, cmd_type, params);
            if (parse_status != STATUS_OK) {
                send_response(parse_status, "Invalid command parameters");
                continue;
            }

            if (strcmp(cmd_type, CMD_WRITE_FILE) == 0) {
                ESP_LOGI(TAG, "Writing file: %s (%zu bytes)", 
                         params->filename, params->filesize);
                
                command_status_t write_status = handle_write_file(params);
                if (write_status == STATUS_OK) {
                    send_response(STATUS_OK, "File written successfully");
                } else {
                    send_response(write_status, "Failed to write file");
                }
            }
            // ... gestione altri comandi ...
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

cleanup:
    free(command);
    free(cmd_type);
    free(params);
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