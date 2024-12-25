#ifndef HELLOESP_SERIAL_H
#define HELLOESP_SERIAL_H
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

// Definizioni
#define SERIAL_FILE_BUFFER_SIZE 1024
#define SERIAL_FILE_CHUNK_SIZE 1024

// Comandi
#define CMD_PING "$$$PING$$$"
#define CMD_WRITE_FILE "$$$WRITE_FILE$$$"
#define CMD_READ_FILE  "$$$READ_FILE$$$"
#define CMD_LIST_FILES "$$$LIST_FILES$$$"
#define CMD_DELETE_FILE "$$$DELETE_FILE$$$"
#define CMD_CHECK_FILE "$$$CHECK_FILE$$$"
#define CMD_CHUNK "$$$CHUNK$$$"
#define CMD_CMD "$$$CMD$$$"
#define CMD_RESET "$$$RESET$$$"
#define CMD_SILENCE_ON "$$$SILENCE_ON$$$"
#define CMD_SILENCE_OFF "$$$SILENCE_OFF$$$"

// Debug
#define HELLO_DEBUG_CMD false

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

typedef struct command_params {
    char filename[MAX_FILENAME];
    bool has_filename;
    size_t filesize;
    char file_hash[33];
    size_t chunk_size;
    char chunk_hash[33]; // todo: merge with file_hash?
    char* cmdline;
} command_params_t;

////////////////////////////////
void begin_exclusive_serial();
void end_exclusive_serial();
char serial_read_char();
char serial_read_char_or_null();
command_status_t wait_content(char* content, command_params_t* params);
command_status_t wait_for_command(char* cmd_type, command_params_t* params);
void serial_handler_task(void *pvParameters);
esp_err_t start_serial_handler(void);
#endif