#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

// Comandi di lettura file
#define CMD_READ_FILE "READ_FILE"
#define CMD_LIST_FILES "LIST_FILES"
#define CMD_DELETE_FILE "DELETE_FILE"
#define CMD_CHECK_FILE "CHECK_FILE"
#define CHUNK_SIZE 1024

#include <dirent.h>
#include "mbedtls/md5.h"

// Definizioni
#define BUF_SIZE 1024
#define MAX_FILENAME 256
#define STACK_SIZE (8192)

// Comandi
#define CMD_WRITE_FILE "$$$WRITE_FILE$$$"
#define CMD_READ_FILE  "$$$READ_FILE$$$"
#define CMD_LIST_FILES "$$$LIST_FILES$$$"
#define CMD_DELETE_FILE "$$$DELETE_FILE$$$"
#define CMD_CHECK_FILE "$$$CHECK_FILE$$$"

// Codici di risposta
typedef enum {
    STATUS_OK = 0,
    STATUS_ERROR_OPEN,
    STATUS_ERROR_WRITE,
    STATUS_ERROR_READ,
    STATUS_ERROR_MEMORY,
    STATUS_ERROR_PARAMS,
    STATUS_ERROR_NOT_FOUND,
    STATUS_ERROR
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


// Helper function per calcolare MD5 di un file
static command_status_t calculate_file_md5(const char* filename, char* hash_out) {
    FILE *file = fopen(filename, "rb");
    if (!file) {
        return STATUS_ERROR;
    }

    mbedtls_md5_context md5_ctx;
    mbedtls_md5_init(&md5_ctx);
    mbedtls_md5_starts(&md5_ctx);

    unsigned char buffer[1024];
    size_t bytes;
    while ((bytes = fread(buffer, 1, sizeof(buffer), file)) != 0) {
        mbedtls_md5_update(&md5_ctx, buffer, bytes);
    }

    unsigned char digest[16];
    mbedtls_md5_finish(&md5_ctx, digest);
    mbedtls_md5_free(&md5_ctx);
    fclose(file);

    for(int i = 0; i < 16; i++) {
        sprintf(&hash_out[i*2], "%02x", (unsigned int)digest[i]);
    }
    hash_out[32] = '\0';

    return STATUS_OK;
}

// Funzione per la scrittura del file
static command_status_t handle_write_file(const command_params_t* params) {
    FILE* f = fopen(params->filename, "w");
    if (f == NULL) {
        ESP_LOGE(TAG, "handle_write_file: STATUS_ERROR_OPEN");
        return STATUS_ERROR_OPEN;
    }

    char* buf = malloc(BUF_SIZE);
    if (!buf) {
        fclose(f);
        ESP_LOGE(TAG, "handle_write_file: STATUS_ERROR_MEMORY");
        return STATUS_ERROR_MEMORY;
    }

    size_t remaining = params->filesize;
    command_status_t status = STATUS_OK;

    while (remaining > 0) {
        size_t to_read = (remaining > BUF_SIZE) ? BUF_SIZE : remaining;
        size_t received = fread(buf, 1, to_read, stdin);

        if (received > 0) {
            if (fwrite(buf, 1, received, f) != received) {
                ESP_LOGE(TAG, "handle_write_file: STATUS_ERROR_WRITE");
                status = STATUS_ERROR_WRITE;
                break;
            }
            remaining -= received;
        } else {
            ESP_LOGE(TAG, "handle_write_file: STATUS_ERROR_READ");
            status = STATUS_ERROR_READ;
            break;
        }
    }

    free(buf);
    fclose(f);
    return status;
}

// Funzione per il parsing dei comandi
static command_status_t parse_command(const char* command, char* cmd_type, command_params_t* params) {
    if (strncmp(command, CMD_WRITE_FILE, strlen(CMD_WRITE_FILE)) == 0) {
        strcpy(cmd_type, CMD_WRITE_FILE);
        if (sscanf(command + strlen(CMD_WRITE_FILE), "%[^,],%zu",
                   params->filename, &params->filesize) != 2) {
            return STATUS_ERROR_PARAMS;
        }
    } else if (strncmp(command, CMD_READ_FILE, strlen(CMD_READ_FILE)) == 0) {
        strcpy(cmd_type, CMD_READ_FILE);
        if (sscanf(command + strlen(CMD_READ_FILE), "%s", params->filename) != 1) {
            return STATUS_ERROR_PARAMS;
        }
    }
    else if (strncmp(command, CMD_LIST_FILES, strlen(CMD_LIST_FILES)) == 0) {
        strcpy(cmd_type, CMD_LIST_FILES);
    }    
    else if(strncmp(command, CMD_DELETE_FILE, strlen(CMD_DELETE_FILE) == 0)) {
        strcpy(cmd_type, CMD_DELETE_FILE);
        if (sscanf(command + strlen(CMD_DELETE_FILE), "%s", params->filename) != 1) {
            return STATUS_ERROR_PARAMS;
        }
    }
    else if(strncmp(command, CMD_CHECK_FILE, strlen(CMD_CHECK_FILE) == 0)) {
        strcpy(cmd_type, CMD_CHECK_FILE);
        if (sscanf(command + strlen(CMD_CHECK_FILE), "%s", params->filename) != 1) {
            return STATUS_ERROR_PARAMS;
        }
    }

    // ... altri comandi ...
    return STATUS_OK;
}

// Helper function per validare il nome del file
static bool is_filename_valid(const char* filename) {
    const char* invalid_chars = "\\/:*?\"<>|";
    
    if (!filename) return false;
    
    // Controlla caratteri non validi
    if (strpbrk(filename, invalid_chars) != NULL) {
        return false;
    }
    
    // Controlla che non inizi con punto o spazio
    if (filename[0] == '.' || filename[0] == ' ') {
        return false;
    }
    
    return true;
}

// Funzione per la scrittura del file
void serial_handler_task(void *pvParameters) {
    char* command = malloc(BUF_SIZE);
    char* cmd_type = malloc(BUF_SIZE);
    command_params_t* params = malloc(sizeof(command_params_t));
    struct stat file_stat;

    if (!command || !cmd_type || !params) {
        ESP_LOGE(TAG, "Failed to allocate buffers");
        goto cleanup;
    }

    ESP_LOGI(TAG, "Serial handler started");

    while(1) {
        if (uxTaskGetStackHighWaterMark(NULL) < 512) {
            ESP_LOGW(TAG, "Stack getting low! %d bytes remaining",
                     uxTaskGetStackHighWaterMark(NULL));
        }

        if (fgets(command, BUF_SIZE, stdin) != NULL) {
            command[strcspn(command, "\n")] = 0;

            if(false){ // debug echo
                ESP_LOGW(TAG, "Command: %s", command);
                continue;
            }
            
            command_status_t parse_status = parse_command(command, cmd_type, params);
            if (parse_status != STATUS_OK) {
                send_response(parse_status, "Invalid command parameters");
                continue;
            }

            if (strcmp(cmd_type, CMD_WRITE_FILE) == 0) {
                // Validazione parametri
                if (!params->filesize) {
                    send_response(STATUS_ERROR, "Missing filename or filesize");
                    continue;
                }

                // Controllo lunghezza nome file
                if (strlen(params->filename) > MAX_FILENAME) { // stupid, it was MAX_FILENAME_LENGTH ... (or MAX_FILENAME)
                    send_response(STATUS_ERROR, "Filename too long");
                    continue;
                }

                // Controllo caratteri validi nel nome file
                if (!is_filename_valid(params->filename)) {
                    char text [286];
                    sprintf(text, "Invalid filename characters: %s\n", params->filename);             
                    send_response(STATUS_ERROR, text);
                    continue;
                }

                // Controllo dimensione file
                if (params->filesize > MAX_FILENAME || params->filesize == 0) {
                    send_response(STATUS_ERROR, "Invalid file size");
                    continue;
                }

                // Controllo spazio disponibile su SD
                FATFS *fs;
                DWORD fre_clust;
                if (f_getfree(SD_MOUNT_POINT, &fre_clust, &fs) == FR_OK) {
                    uint64_t free_space = (uint64_t)fre_clust * fs->csize * 512;
                    if (params->filesize > free_space) {
                        send_response(STATUS_ERROR, "Not enough space on SD card");
                        continue;
                    }
                }

                // Controllo esistenza file
                if (stat(params->filename, &file_stat) == 0) {
                    char msg[64];
                    snprintf(msg, sizeof(msg), 
                            "File exists with size: %ld bytes", 
                            file_stat.st_size);
                    send_response(STATUS_ERROR, msg);
                    continue;
                }

                ESP_LOGI(TAG, "Writing file: %s (%zu bytes)", 
                         params->filename, params->filesize);
                
                command_status_t write_status = handle_write_file(params);
                if (write_status == STATUS_OK) {
                    // Verifica integrità dopo scrittura
                    if (stat(params->filename, &file_stat) == 0) {
                        if (file_stat.st_size != params->filesize) {
                            send_response(STATUS_ERROR, "File size mismatch after write");
                            continue;
                        }
                    }
                    send_response(STATUS_OK, "File written successfully");
                } else {
                    send_response(write_status, "Failed to write file");
                }
            }
            else if (strcmp(cmd_type, CMD_CHECK_FILE) == 0) {
                // Controllo esistenza file
                if (stat(params->filename, &file_stat) != 0) {
                    send_response(STATUS_ERROR, "0: File not found");                   
                }
                else {
                    char resp [128];
                    sprintf(resp, "%ld: File found", file_stat.st_size);            
                    send_response(STATUS_OK, "1: File found");
                }                
                continue;
            }
            else if (strcmp(cmd_type, CMD_READ_FILE) == 0) {
                /*if (!params->filename) { // always true
                    send_response(STATUS_ERROR, "Missing filename");
                    continue;
                }*/

                // Controllo esistenza file
                if (stat(params->filename, &file_stat) != 0) {
                    send_response(STATUS_ERROR, "File not found");
                    continue;
                }

                // Calcolo e invio hash MD5 del file
                char hash[33];
                if (calculate_file_md5(params->filename, hash) != STATUS_OK) {
                    send_response(STATUS_ERROR, "Failed to calculate file hash");
                    continue;
                }

                // Invia dimensione file e hash
                char response[100];
                snprintf(response, sizeof(response), "%ld,%s", file_stat.st_size, hash);
                send_response(STATUS_OK, response);

                // Leggi e invia il file a chunks
                FILE *f = fopen(params->filename, "rb");
                if (!f) {
                    send_response(STATUS_ERROR, "Failed to open file");
                    continue;
                }

                uint8_t *chunk = malloc(CHUNK_SIZE);
                if (!chunk) {
                    fclose(f);
                    send_response(STATUS_ERROR, "Failed to allocate chunk buffer");
                    continue;
                }

                size_t bytes_sent = 0;
                while (bytes_sent < file_stat.st_size) {
                    size_t to_read = MIN(CHUNK_SIZE, file_stat.st_size - bytes_sent);
                    size_t read = fread(chunk, 1, to_read, f);
                    if (read != to_read) {
                        free(chunk);
                        fclose(f);
                        send_response(STATUS_ERROR, "Failed to read file");
                        continue;
                    }

                    // Invia chunk
                    if (fwrite(chunk, 1, read, stdout) != read) {
                        free(chunk);
                        fclose(f);
                        send_response(STATUS_ERROR, "Failed to send chunk");
                        continue;
                    }
                    fflush(stdout);

                    // Attendi ACK
                    char ack[10];
                    if (fgets(ack, sizeof(ack), stdin) == NULL || strncmp(ack, "OK", 2) != 0) {
                        free(chunk);
                        fclose(f);
                        send_response(STATUS_ERROR, "Failed to get chunk ACK");
                        continue;
                    }

                    bytes_sent += read;
                }

                free(chunk);
                fclose(f);
                send_response(STATUS_OK, "File sent successfully");
            }
            else if (strcmp(cmd_type, CMD_LIST_FILES) == 0) {
                DIR *dir;
                struct dirent *ent;
                char file_list[4096] = "";  // Buffer per la lista file
                size_t offset = 0;

                dir = opendir(SD_MOUNT_POINT);
                if (dir == NULL) {
                    send_response(STATUS_ERROR, "Failed to open directory");
                    continue;
                }

                while ((ent = readdir(dir)) != NULL) {
                    // Salta directory . e ..
                    if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) {
                        continue;
                    }

                    // Prendi dimensione file
                    if (stat(ent->d_name, &file_stat) == 0) {
                        int written = snprintf(file_list + offset, 
                                            sizeof(file_list) - offset,
                                            "%s,%ld;", 
                                            ent->d_name, 
                                            file_stat.st_size);
                        if (written > 0) {
                            offset += written;
                        }
                    }
                }
                closedir(dir);

                if (offset > 0) {
                    file_list[offset-1] = '\0';  // Rimuovi ultimo separatore
                }

                send_response(STATUS_OK, file_list);
            }
            else if (strcmp(cmd_type, CMD_DELETE_FILE) == 0) {
                /*if (!params->filename) { // always true
                    send_response(STATUS_ERROR, "Missing filename");
                    continue;
                }*/

                // Controllo esistenza file
                if (stat(params->filename, &file_stat) != 0) {
                    send_response(STATUS_ERROR, "File not found");
                    continue;
                }

                // Prova a eliminare il file
                if (unlink(params->filename) != 0) {
                    send_response(STATUS_ERROR, "Failed to delete file");
                    continue;
                }

                send_response(STATUS_OK, "File deleted successfully");
            }
            else if (strcmp(cmd_type, CMD_CHECK_FILE) == 0) {
                /*if (!params->filename) { // always true
                    send_response(STATUS_ERROR, "Missing filename");
                    continue;
                }*/

                if (stat(params->filename, &file_stat) == 0) {
                    char size_str[20];
                    snprintf(size_str, sizeof(size_str), "%ld", file_stat.st_size);
                    send_response(STATUS_OK, size_str);
                } else {
                    send_response(STATUS_ERROR, "File not found");
                }
            }
            else {
                char text [128];
                sprintf(text, "Unknown command: %s\n", command);                
                send_response(STATUS_ERROR, text);
            }
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