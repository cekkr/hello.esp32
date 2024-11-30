#ifndef HELLOESP_CMD
#define HELLOESP_CMD

#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <ctype.h>

#include "esp_log.h"

// WASM
#include "wasm.h"

#define MAX_ARGS 32
#define MAX_COMMAND_LENGTH 256

typedef struct {
    const char* command;
    int (*handler)(int argc, char** argv);
} command_entry_t;

// Funzione di utilità per rimuovere gli spazi iniziali e finali
static char* trim(char* str) {
    while(isspace((unsigned char)*str)) str++;
    if(*str == 0) return str;
    
    char* end = str + strlen(str) - 1;
    while(end > str && isspace((unsigned char)*end)) end--;
    end[1] = '\0';
    
    return str;
}

// Parser degli argomenti che gestisce le stringhe tra virgolette
static int parse_arguments(char* input, char** argv) {
    int argc = 0;
    bool in_quotes = false;
    char* p = input;
    char* token_start = input;
    
    while (*p && argc < MAX_ARGS - 1) {
        if (*p == '"') {
            if (!in_quotes) {
                token_start = p + 1;
            } else {
                *p = '\0';
                argv[argc++] = token_start;
                token_start = p + 1;
            }
            in_quotes = !in_quotes;
        } else if (isspace((unsigned char)*p) && !in_quotes) {
            if (p > token_start) {
                *p = '\0';
                argv[argc++] = token_start;
            }
            token_start = p + 1;
        }
        p++;
    }
    
    // Gestisce l'ultimo token se presente
    if (p > token_start && argc < MAX_ARGS - 1) {
        argv[argc++] = token_start;
    }
    
    argv[argc] = NULL;
    return argc;
}

// Handler per il comando "run"
static int cmd_run(int argc, char** argv) {
    if (argc < 2) {
        ESP_LOGI(TAG, "Usage: run <filename> [args...]\n");
        return -1;
    }
    
    //todo: implement arguments
    ESP_LOGI(TAG, "Executing file: %s\n", argv[1]);
    for (int i = 2; i < argc; i++) {
        ESP_LOGI(TAG, "Arg %d: %s\n", i-1, argv[i]);
    }

    // Append SD mount path
    char* fullpath = malloc(sizeof(char)*MAX_FILENAME);
    sprintf(fullpath, "%s/%s", SD_MOUNT_POINT, argv[0]);

    // Get program
    uint8_t* data = NULL;
    size_t size = 0;
    esp_err_t result = read_file_to_memory(fullpath, &data, &size);

    if (result == ESP_OK) {
        // WASM execution
        run_wasm(data, size);

        free(data);
    } else {
        ESP_LOGI(TAG, "Errore nella lettura del file: %d\n", result);
        return -1;
    }    

    return 0;
}

// Handler per il comando "echo"
static int cmd_echo(int argc, char** argv) {
    for (int i = 1; i < argc; i++) {
        ESP_LOGI(TAG, "%s ", argv[i]);
    }
    ESP_LOGI(TAG, "\n");
    return 0;
}

// Handler per il comando "ls"
static int cmd_ls(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : ".";
    ESP_LOGI(TAG, "Listing directory: %s\n", path);
    // Implementare la logica per listare i file
    return 0;
}

// Tabella dei comandi supportati
static const command_entry_t commands[] = {
    {"run", cmd_run},
    {"echo", cmd_echo},
    {"ls", cmd_ls},
    {NULL, NULL}  // Terminatore
};

// Funzione principale per l'elaborazione dei comandi
int process_command(char* cmd_str) {
    char* argv[MAX_ARGS];
    char cmd_copy[MAX_COMMAND_LENGTH];
    
    // Copia il comando per non modificare l'originale
    strncpy(cmd_copy, cmd_str, MAX_COMMAND_LENGTH - 1);
    cmd_copy[MAX_COMMAND_LENGTH - 1] = '\0';
    
    // Rimuove spazi iniziali e finali
    char* trimmed_cmd = trim(cmd_copy);
    
    // Parsing degli argomenti
    int argc = parse_arguments(trimmed_cmd, argv);
    if (argc == 0) return 0;
    
    // Cerca il comando nella tabella
    for (const command_entry_t* cmd = commands; cmd->command != NULL; cmd++) {
        if (strcmp(argv[0], cmd->command) == 0) {
            return cmd->handler(argc, argv);
        }
    }
    
    ESP_LOGI(TAG, "Unknown command: %s\n", argv[0]);
    return -1;
}

#endif