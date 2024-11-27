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
#define CMD_CHUNK "$$$CHUNK$$$"

// Codici di risposta
typedef enum {
    STATUS_OK = 0,
    STATUS_ERROR_OPEN,
    STATUS_ERROR_WRITE,
    STATUS_ERROR_READ,
    STATUS_ERROR_MEMORY,
    STATUS_ERROR_PARAMS,
    STATUS_ERROR_NOT_FOUND,
    STATUS_ERROR_TIMEOUT,
    STATUS_ERROR_BUFFER,
    STATUS_ERROR
} command_status_t;

// Struttura per i parametri del comando
typedef struct {
    char filename[MAX_FILENAME];
    size_t filesize;
    char file_hash[33];
    size_t chunk_size;
    char chunk_hash[33];
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

static void calculate_md5_hex(const unsigned char* digest, char* hash_out) {
    for(int i = 0; i < 16; i++) {
        sprintf(&hash_out[i*2], "%02x", (unsigned int)digest[i]);
    }
    hash_out[32] = '\0';
}

static void calculate_md5(const unsigned char* data, size_t len, char* hash_out) {
    mbedtls_md5_context md5_ctx;
    mbedtls_md5_init(&md5_ctx);
    mbedtls_md5_starts(&md5_ctx);
    mbedtls_md5_update(&md5_ctx, data, len);
    
    unsigned char digest[16];
    mbedtls_md5_finish(&md5_ctx, digest);
    mbedtls_md5_free(&md5_ctx);
    
    calculate_md5_hex(digest, hash_out);
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
        if (sscanf(command + strlen(CMD_WRITE_FILE), "%[^,],%zu,%32s",
                params->filename, &params->filesize, params->file_hash) != 3) {
            return STATUS_ERROR_PARAMS;
        }
    }
    else if (strncmp(command, CMD_CHUNK, strlen(CMD_CHUNK)) == 0) {
        strcpy(cmd_type, CMD_CHUNK);
        if (sscanf(command + strlen(CMD_CHUNK), "%zu,%32s",
                &params->chunk_size, params->chunk_hash) != 2) {
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
    else if(strncmp(command, CMD_DELETE_FILE, strlen(CMD_DELETE_FILE)) == 0) {
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

command_status_t wait_for_command(char* cmd_type, command_params_t* params) {
    char command_buffer[256] = {0};
    size_t length = 0;
    
    while (length < sizeof(command_buffer) - 1) {
        char c = getchar();
        if (c == EOF) {
            return STATUS_ERROR_TIMEOUT;
        }
        
        if (c == '\n') {
            command_buffer[length] = '\0';
            break;
        }
        
        command_buffer[length++] = c;
    }
    
    if (length == sizeof(command_buffer) - 1) {
        return STATUS_ERROR_BUFFER;
    }
    
    return parse_command(command_buffer, cmd_type, params);
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
                if (params->filesize > (1024*1024*32) || params->filesize == 0) {
                    send_response(STATUS_ERROR, "Invalid file size");
                    continue;
                }

                FILE* file = fopen(params->filename, "wb");
                if (!file) {
                    send_response(STATUS_ERROR, "Failed to create file");
                    continue;
                }

                size_t total_received = 0;
                uint8_t chunk_buffer[1024];
                char calculated_hash[33];
                mbedtls_md5_context md5_ctx;
                mbedtls_md5_init(&md5_ctx);
                mbedtls_md5_starts(&md5_ctx);

                send_response(STATUS_OK, "Ready for chunks");

                while (total_received < params->filesize) {
                    // Attendi comando chunk
                    if (wait_for_command(cmd_type, params) != STATUS_OK ||
                        strcmp(cmd_type, CMD_CHUNK) != 0) {
                        fclose(file);
                        unlink(params->filename);
                        send_response(STATUS_ERROR, "Invalid chunk command");
                        continue;
                    }

                    // Leggi e verifica chunk
                    size_t to_read = params->chunk_size;
                    size_t total_read = 0;

                    while (total_read < to_read) {
                        int c = getchar();
                        if (c == EOF) {
                            fclose(file);
                            unlink(params->filename); 
                            send_response(STATUS_ERROR, "Failed to read chunk data");
                            continue;
                        }
                        chunk_buffer[total_read++] = (uint8_t)c;
                    }

                    // Verifica hash chunk
                    calculate_md5(chunk_buffer, read, calculated_hash);
                    if (strcmp(calculated_hash, params->chunk_hash) != 0) {
                        fclose(file);
                        unlink(params->filename);
                        send_response(STATUS_ERROR, "Chunk hash mismatch");
                        continue;
                    }

                    // Aggiorna hash totale e scrivi
                    mbedtls_md5_update(&md5_ctx, chunk_buffer, read);
                    fwrite(chunk_buffer, 1, read, file);
                    total_received += read;

                    send_response(STATUS_OK, "Chunk received");
                }

                // Verifica hash finale
                uint8_t hash_result[16];
                mbedtls_md5_finish(&md5_ctx, hash_result);
                mbedtls_md5_free(&md5_ctx);
                calculate_md5_hex(hash_result, calculated_hash);

                fclose(file);

                if (strcmp(calculated_hash, params->file_hash) != 0) {
                    unlink(params->filename);
                    send_response(STATUS_ERROR, "File hash mismatch");
                } else {
                    send_response(STATUS_OK, "File written successfully");
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
                char file_list[4096] = "LIST:";  // Buffer per la lista file
                size_t offset = 5;

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
                    file_list[offset] = '\0';  // Rimuovi ultimo separatore
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