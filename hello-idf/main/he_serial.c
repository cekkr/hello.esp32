#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <errno.h>
#include "driver/uart.h"     // Per UART_NUM_0 e altre costanti UART
#include "esp_task_wdt.h"
#include <dirent.h>
#include "mbedtls/md5.h"
#include "he_defines.h"
#include "he_device.h"
#include "he_sdcard.h"
#include "he_monitor.h"

#include "he_serial.h"
#include "he_cmd.h"

void serial_write(const char* data, size_t len){
    uart_write_bytes(UART_NUM_0, data, len);
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
}

void serial_write_auto(const char* data) {
    uart_write_bytes(UART_NUM_0, data, strlen(data));
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);    
}

void begin_exclusive_serial() {
    if(!exclusive_serial_mode){
        exclusive_serial_mode = true;
        esp_log_level_set("*", ESP_LOG_NONE);
    }
}

void end_exclusive_serial() {
    if(exclusive_serial_mode){
        exclusive_serial_mode = false;
        enable_log_debug();
    }
}

char serial_read_char(){
    char c = '\0';
    const TickType_t timeout = pdMS_TO_TICKS(10); // 10ms timeout // or portMAX_DELAY

    while(true){
        if(uart_read_bytes(UART_NUM_0, &c, 1, timeout) > 0){
            break;            
        }
        else {
            vTaskDelay(timeout);
        }

        WATCHDOG_RESET
    }

    return c;
}

char serial_read_char_or_null() {
    char c = '\0';
    const TickType_t timeout = pdMS_TO_TICKS(10); // 10ms timeout
    
    // Legge un byte con timeout
    size_t bytes_read = uart_read_bytes(UART_NUM_0, &c, 1, timeout);
    
    // Resetta il watchdog ad ogni tentativo
    WATCHDOG_RESET;
    
    // Restituisce '\0' se non ci sono dati, altrimenti il carattere letto
    return (bytes_read == 0) ? '\0' : c;
}

///
///
///

// Funzione per inviare la risposta
static void send_response(command_status_t status, const char* message) {
    char buffer[1024];
    switch(status) {
        case STATUS_OK:
            sprintf(buffer, "OK: %s\n", message);            
            break;
        default:
            sprintf(buffer, "ERROR: %s\n", message);
            break;
    }

    serial_write(buffer, strlen(buffer));    
}

///
///
///



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

    char* buf = malloc(SERIAL_FILE_BUFFER_SIZE);
    if (!buf) {
        fclose(f);
        ESP_LOGE(TAG, "handle_write_file: STATUS_ERROR_MEMORY");
        return STATUS_ERROR_MEMORY;
    }

    size_t remaining = params->filesize;
    command_status_t status = STATUS_OK;

    while (remaining > 0) {
        size_t to_read = (remaining > SERIAL_FILE_BUFFER_SIZE) ? SERIAL_FILE_BUFFER_SIZE : remaining;
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

///
///
///

// to be used: timeout not implemented
command_status_t wait_content(char* content, command_params_t* params) {
    char command_buffer[1536] = {0};
    size_t length = 0;
    
    while (length < sizeof(command_buffer) - 1 && length < params->chunk_size) {
        char c = getchar();               
        command_buffer[length++] = c;
    }
    
    return STATUS_OK;
}

// Funzione per il parsing dei comandi
static command_status_t parse_command(const char* command, char* cmd_type, command_params_t* params) {    

    if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Parsing command: %s\n", command);

    //ESP_LOGI(TAG, "PING strncmp: %s = %d\n", command, strncmp(command, CMD_PING, strlen(CMD_PING)));

    if (strncmp(command, CMD_PING, strlen(CMD_PING)) == 0) {
        strcpy(cmd_type, CMD_PING);
    }
    else if (strncmp(command, CMD_WRITE_FILE, strlen(CMD_WRITE_FILE)) == 0) {
        strcpy(cmd_type, CMD_WRITE_FILE);

        char filename[MAX_FILENAME];
        if (sscanf(command + strlen(CMD_WRITE_FILE), 
                "%255[^,],%zu,%32s",  // Limitare la lunghezza di lettura
                filename,
                &params->filesize, 
                params->file_hash) != 3) {
            return STATUS_ERROR_PARAMS;
        }
        params->has_filename = true;

        if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Writing path: %s\n", params->filename);
    }
    else if (strncmp(command, CMD_CHUNK, strlen(CMD_CHUNK)) == 0) {
        strcpy(cmd_type, CMD_CHUNK);
        if (sscanf(command + strlen(CMD_CHUNK), "%zu,%32s",
                &params->chunk_size, params->chunk_hash) != 2) {
            return STATUS_ERROR_PARAMS;
        }
    } else if (strncmp(command, CMD_READ_FILE, strlen(CMD_READ_FILE)) == 0) {
        strcpy(cmd_type, CMD_READ_FILE);

        char filename[MAX_FILENAME];
        if (sscanf(command + strlen(CMD_READ_FILE), "%s", filename) != 1) {
            return STATUS_ERROR_PARAMS;
        }
        params->has_filename = true;
    }
    else if (strncmp(command, CMD_LIST_FILES, strlen(CMD_LIST_FILES)) == 0) {
        strcpy(cmd_type, CMD_LIST_FILES);
    }    
    else if(strncmp(command, CMD_DELETE_FILE, strlen(CMD_DELETE_FILE)) == 0) {
        strcpy(cmd_type, CMD_DELETE_FILE);

        char filename[MAX_FILENAME];
        if (sscanf(command + strlen(CMD_DELETE_FILE), "%s", filename) != 1) {            
            return STATUS_ERROR_PARAMS;
        }
        params->has_filename = true;
    }
    else if(strncmp(command, CMD_CHECK_FILE, strlen(CMD_CHECK_FILE)) == 0) {
        strcpy(cmd_type, CMD_CHECK_FILE);

        char filename[MAX_FILENAME];
        if (sscanf(command + strlen(CMD_CHECK_FILE), "%s", filename) != 1) {            
            return STATUS_ERROR_PARAMS;
        }
        params->has_filename = true;
    }
    else if(strncmp(command, CMD_CMD, strlen(CMD_CMD)) == 0) {
        strcpy(cmd_type, CMD_CMD);

        char* cmd = malloc(sizeof(char) * MAX_CMD_LENGTH);
        if (sscanf(command + strlen(CMD_CMD), " %[^]]", cmd) != 1) {
            return STATUS_ERROR_PARAMS;
        }

        params->cmdline = cmd;
    } 
    else if(strncmp(command, CMD_RESET, strlen(CMD_RESET)) == 0) {
        strcpy(cmd_type, CMD_RESET);
    }
    else if(strncmp(command, CMD_SILENCE_OFF, strlen(CMD_SILENCE_OFF)) == 0) {
        strcpy(cmd_type, CMD_SILENCE_OFF);
    }
     else if(strncmp(command, CMD_SILENCE_ON, strlen(CMD_SILENCE_ON)) == 0) {
        strcpy(cmd_type, CMD_SILENCE_ON);
    }

    // ... altri comandi ...
    return STATUS_OK;
}

command_status_t wait_for_command(char* cmd_type, command_params_t* params) {    
    char command_buffer[1536] = {0};
    size_t length = 0;
    
    int incipit = 0;
    while (length < sizeof(command_buffer) - 1) {
        //char c = getchar();        

        char c = serial_read_char();    

        WATCHDOG_RESET

        //if (uart_read_bytes(UART_NUM_0, &c, 1, portMAX_DELAY) > 0) {

        if(incipit == 0){
            if(c == 0xFF || c == '\0' || c != '$'){
                vTaskDelay(0.01);            
                continue;
            }
            else if(c != '$'){
                vTaskDelay(0.01);
                continue;
            }
        }

        if(c == '$'){
            incipit++;
        }
        
        if (incipit < 3 && length > 3){
            command_buffer[length] = '\0';
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "wait_for_command: reset (%s) (length: %d) (incipit: %d)\n", command_buffer, length, incipit);
            incipit = 0;
            length = 0;
            continue;
        }

        if (c == EOF) {
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "wait_for_command: EOF\n");
            command_buffer[length] = '\0';
            return STATUS_ERROR_TIMEOUT;
        }
        
        if (c == '\n') {            
            command_buffer[length] = '\0';
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "wait_for_command: end (%d) '%s'\n", sizeof(command_buffer), command_buffer);
            break;
        }
        
        command_buffer[length++] = c;

        //}
    }
    
    if (length == sizeof(command_buffer) - 1) {
        return STATUS_ERROR_BUFFER;
    }
    
    command_status_t res = parse_command(command_buffer, cmd_type, params);

    if(res == STATUS_OK) {
        if(strncmp(cmd_type, CMD_PING, strlen(CMD_PING)) == 0){
            send_response(STATUS_OK, "PONG");
            return wait_for_command(cmd_type, params);
        }
    }

    return res;
}


// Helper function per validare il nome del file
static bool is_filename_valid(const char* filename) {
    const char* invalid_chars = ":*?\"<>|"; // rimossi / e back
    
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
    WATCHDOG_ADD

    //char* command = malloc(SERIAL_FILE_BUFFER_SIZE);
    char* cmd_type = malloc(SERIAL_FILE_BUFFER_SIZE);
    
    command_params_t* params = malloc(sizeof(command_params_t));
    memset(params, 0, sizeof(command_params_t));

    struct stat file_stat;

    char text [512];

    if (!cmd_type || !params) { // || !command
        ESP_LOGE(TAG, "Failed to allocate buffers\n");
        goto cleanup;
    }

    ////////////////////////////////
    // Init shell
    shell_t shell = { 0 };
    //shell_init(&shell); // useless

    shell.cwd = malloc(MAX_FILENAME*sizeof(char));
    if (!shell.cwd) {
        ESP_LOGE(TAG, "Failed to allocate memory for shell.cwd\n");
        goto cleanup;
    }

    strcpy(shell.cwd, SD_MOUNT_POINT);
    strcat(shell.cwd, "/");

    ////////////////////////////////

    ESP_LOGI(TAG, "Serial handler started\n");

    while(1) {        
        WATCHDOG_RESET

        if (uxTaskGetStackHighWaterMark(NULL) < 512) {
            ESP_LOGW(TAG, "Stack getting low! %d bytes remaining\n",
                     uxTaskGetStackHighWaterMark(NULL));
        }
        
        end_exclusive_serial();

        if(params->cmdline != NULL){
            free(params->cmdline);
            params->cmdline = NULL;
        }

        params->has_filename = false;
        command_status_t parse_status = wait_for_command(cmd_type, params);

        if(params->has_filename) {
            prepend_cwd(shell.cwd, params->filename);
        }

        if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Working on cmd_type: %s\n", cmd_type);

        if (parse_status != STATUS_OK) {
            sprintf(text, "Invalid command parameters: %s", cmd_type);             
            send_response(parse_status, text);
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
                sprintf(text, "Invalid filename characters: %s", params->filename);             
                send_response(STATUS_ERROR, text);
                continue;
            }

            // Controllo dimensione file
            if (params->filesize > (1024*1024*32) || params->filesize == 0) {
                sprintf(text, "Invalid file size: %d", params->filesize);             
                send_response(STATUS_ERROR, text);
                continue;
            }

            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Starting reading file...\n");
            FILE* file = fopen(params->filename, "w");
            if (!file) {
                char text[FILENAME_MAX + 128];
                sprintf(text, "Failed to create file %s: %s", 
                        params->filename, strerror(errno));
                send_response(STATUS_ERROR, text);
                continue;
            }

            monitor_disable();

            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Calculating MD5\n");
            size_t total_received = 0;
            uint8_t chunk_buffer[1024];
            char calculated_hash[33];
            mbedtls_md5_context md5_ctx;
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "mbedtls_md5_init\n");
            mbedtls_md5_init(&md5_ctx);
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "mbedtls_md5_init\n");
            mbedtls_md5_starts(&md5_ctx);
            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "mbedtls_md5_init COMPLETE\n");      

            sprintf(text, "OK:READY: Wait for chunks");    
            send_response(STATUS_OK, text);                  

            bool chunkHashFailed = false;
            int invalidChunkCmds = 0;
            while (total_received < params->filesize) {
                // Attendi comando chunk

                char* cmd_type_chunk = malloc(SERIAL_FILE_BUFFER_SIZE);
                command_params_t* params_chunk = malloc(sizeof(command_params_t));
                if (wait_for_command(cmd_type_chunk, params_chunk) != STATUS_OK || strcmp(cmd_type_chunk, CMD_CHUNK) != 0) {
                    fclose(file);
                    unlink(params->filename);

                    sprintf(text, "Invalid chunk command: %s", cmd_type_chunk);             
                    send_response(STATUS_ERROR, text);

                    if(invalidChunkCmds++ > 3){
                        send_response(STATUS_ERROR, "Too many invalid chunk commands");
                        break;
                    }

                    continue;
                }    
                else {
                    sprintf(text, "OK:READY: Ready for chunk (%d)", params->filesize);    
                    send_response(STATUS_OK, text);
                }            

                // Leggi e verifica chunk
                size_t to_read = params_chunk->chunk_size;
                size_t total_read = 0;

                if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Starting reading chunk of size %d\n", to_read);

                while (total_read < to_read) {
                    //ESP_LOGI(TAG, "serial_read_char()\n");
                    int c = serial_read_char();
                    WATCHDOG_RESET
                    //ESP_LOGI(TAG, "serial_read_char() complete: %c\n", c);

                    if (c == EOF) {
                        fclose(file);
                        unlink(params->filename); 
                        send_response(STATUS_ERROR, "Failed to read chunk data");                        
                        break;
                    }
                    chunk_buffer[total_read++] = (uint8_t)c;
                }

                // Verifica hash chunk
                total_received += to_read;
                if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Read %d of %d\n", total_received, params->filesize);
                if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Verifying chunk MD5\n");
                calculate_md5(chunk_buffer, total_read, calculated_hash);
                if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "calculate_md5 done.\n");
                if (strcmp(calculated_hash, params_chunk->chunk_hash) != 0) {
                    fclose(file);
                    unlink(params->filename);
                    send_response(STATUS_ERROR, "Chunk hash mismatch");
                    chunkHashFailed = true;                    
                    break;
                }

                // Aggiorna hash totale e scrivi
                mbedtls_md5_update(&md5_ctx, chunk_buffer, total_read);
                fwrite(chunk_buffer, sizeof(chunk_buffer[0]), total_received, file);                

                send_response(STATUS_OK, "Chunk received");                
            }

            if(chunkHashFailed){                
                continue;
            }

            if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "All data received\n");

            if(true){ // IGNORE_FINAL_FILE_HASH 
                // Verifica hash finale
                uint8_t hash_result[16];
                mbedtls_md5_finish(&md5_ctx, hash_result);
                mbedtls_md5_free(&md5_ctx);
                calculate_md5_hex(hash_result, calculated_hash);

                fclose(file);

                if(HELLO_DEBUG_CMD) ESP_LOGI(TAG, "Verifying total hash...\n");
                if (strcmp(calculated_hash, params->file_hash) != 0) {
                    unlink(params->filename);
                    send_response(STATUS_ERROR, "File hash mismatch");
                } else {
                    send_response(STATUS_OK, "File written successfully");
                }
            }
            else {
                fclose(file);
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

            uint8_t *chunk = malloc(SERIAL_FILE_CHUNK_SIZE);
            if (!chunk) {
                fclose(f);
                send_response(STATUS_ERROR, "Failed to allocate chunk buffer");
                continue;
            }

            monitor_disable();

            size_t bytes_sent = 0;
            while (bytes_sent < file_stat.st_size) {
                size_t to_read = MIN(SERIAL_FILE_CHUNK_SIZE, file_stat.st_size - bytes_sent);
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

            end_exclusive_serial();

            free(chunk);
            fclose(f);
            send_response(STATUS_OK, "File sent successfully");
        }
        else if (strcmp(cmd_type, CMD_LIST_FILES) == 0) {
            monitor_disable();

            // Analyze the mounting point
            if(false){
                struct stat st;
                if (stat(SD_MOUNT_POINT, &st) != 0) {
                    sprintf(text, "Mount point error: %s", strerror(errno));            
                    send_response(STATUS_ERROR, text);
                    continue;
                }
    
                ESP_LOGI(TAG, "Directory permissions: %lo\n", st.st_mode & 0777);   
            }         

            ////////////////////////////////
            DIR *dir;
            struct dirent *ent;
            char file_list[4096] = "LIST:";  // Buffer per la lista file
            size_t offset = 5;                

            dir = opendir(SD_MOUNT_POINT);
            if (dir == NULL) {
                send_response(STATUS_ERROR, "Failed to open directory");
                continue;
            }            

            char fullpath[MAX_FILENAME+64];
            while ((ent = readdir(dir)) != NULL) {
                // Salta directory . e ..
                if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) {
                    continue;
                }

                sprintf(fullpath, "%s/%s", SD_MOUNT_POINT, ent->d_name);

                // Prendi dimensione file
                if (stat(fullpath, &file_stat) == 0) {
                    int written = snprintf(file_list + offset, 
                                        sizeof(file_list) - offset,
                                        "%s,%ld;", 
                                        ent->d_name, 
                                        file_stat.st_size);
                    if (written > 0) {
                        offset += written;
                    }
                }
                else {         
                    ESP_LOGE(TAG, "File %s stat error: %s", fullpath, strerror(errno));                    
                }
            }
            closedir(dir);

            if (offset > 0) {
                offset++;
                file_list[offset] = '\0';  // Rimuovi ultimo separatore
            }

            send_response(STATUS_OK, file_list);
            end_exclusive_serial();
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
        else if(strcmp(cmd_type, CMD_CMD) == 0){
            if(serial_wasm_read){
                if(serial_wasm_read_string != NULL)
                    free(serial_wasm_read_string);

                serial_wasm_read_string = malloc(sizeof(char) * strlen(params->cmdline));
                strcpy(serial_wasm_read_string, params->cmdline);

                serial_wasm_read = false;
                send_response(STATUS_OK, "Command sent to WASM");
                continue;
            }

            send_response(STATUS_OK, "Running command");

            if(settings.disable_serial_monitor_during_run)
                monitor_disable();

            process_command(&shell, params->cmdline);
            free(params->cmdline);

            if(settings.disable_serial_monitor_during_run)
                monitor_enable();
        }
        else if(strcmp(cmd_type, CMD_CHUNK) == 0){
            send_response(STATUS_ERROR, "Chunk out of context");
        }
        else if(strcmp(cmd_type, CMD_RESET) == 0){
            restart_device();
        }
        else if(strcmp(cmd_type, CMD_SILENCE_ON) == 0){
            begin_exclusive_serial();
        }
        else if(strcmp(cmd_type, CMD_SILENCE_OFF) == 0){
            end_exclusive_serial();
        }
        else {
            sprintf(text, "Unknown command: %s", cmd_type);                
            send_response(STATUS_ERROR, text);
        }
    
        vTaskDelay(pdMS_TO_TICKS(10));
    }

cleanup:
    //free(command);
    free(cmd_type);
    free(params);
    shell_cleanup(&shell);

    WATCHDOG_END

    vTaskDelete(NULL);
}

esp_err_t start_serial_handler(void) {
    BaseType_t ret;
    if(SERIAL_TASK_ADV){
        ret = xTaskCreatePinnedToCore(
            serial_handler_task,
            "serial_handler",
            SERIAL_STACK_SIZE,     // Aumentato a 8KB
            NULL,
            5,              // Priorità media
            NULL,           // Non ci serve l'handle
            SERIAL_TASK_CORE               // Core 1
        );
    }
    else {
        ret = xTaskCreate(
            serial_handler_task,
            "serial_handler",
            SERIAL_STACK_SIZE,
            NULL, // params
            5,
            NULL // handler
        );      
    }
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create serial handler task");
        return ESP_FAIL;
    }    
    
    return ESP_OK;
}
