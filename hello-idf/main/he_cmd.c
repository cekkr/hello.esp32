#include "he_cmd.h"

// WASM
#include "he_wasm.h"
#include "he_io.h"

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

////
////
////

// Handler per il comando "run"
static int cmd_run(shell_t* shell, int argc, char** argv) {
    if (argc < 1) {
        ESP_LOGI(TAG, "Usage: run <filename> [args...]\n");
        return -1;
    }
    
    // Preparazione del path e lettura del file come prima
    char* fullpath = malloc(sizeof(char)*MAX_FILENAME);
    sprintf(fullpath, "%s%s", shell->cwd, argv[0]);

    uint8_t* data = NULL;
    size_t size = 0;
    esp_err_t result = read_file_to_executable_memory(fullpath, &data, &size);
    free(fullpath);

    if (result == ESP_OK) {
        int minStackSize = WASM_TASK_SIZE; // was WASM_STACK_SIZE

        // Crea i parametri per la task
        wasm_task_params_t* params = malloc(sizeof(wasm_task_params_t));
        if (params == NULL) {
            ESP_LOGE(TAG, "Errore nell'allocazione dei parametri della task WASM");
            return ESP_ERR_NO_MEM;
        }
        
        params->wasm_data = data;
        params->wasm_size = size;
        
        // Crea la task
        TaskHandle_t task_handle;
        BaseType_t ret;
        const UBaseType_t priority = 5 | portPRIVILEGE_BIT;
        char* error_msg = NULL;

        if (WASM_TASK_ADV) {
            ret = xTaskCreatePinnedToCore(
                wasm_task,
                "wasm_executor",
                minStackSize,     // Stack 8KB
                params,
                priority,
                &task_handle,
                WASM_TASK_CORE
            );
            error_msg = "task pinnata al core";
        } else {
            ret = xTaskCreate(
                wasm_task,
                "wasm_executor",
                minStackSize,
                params,
                priority,
                &task_handle
            );
            error_msg = "task standard";
        }
        
        if (ret != pdPASS) {
            const char* err_reason;
            switch (ret) {
                case errCOULD_NOT_ALLOCATE_REQUIRED_MEMORY:
                    err_reason = "memoria insufficiente";
                    break;
                case errQUEUE_BLOCKED:
                    err_reason = "coda bloccata";
                    break;
                case errQUEUE_YIELD:
                    err_reason = "yield richiesto";
                    break;
                default:
                    err_reason = "errore sconosciuto";
            }
            
            ESP_LOGE(TAG, "Creazione %s fallita: %s (codice: %d)", 
                    error_msg, err_reason, ret);
            
            // Pulizia memoria
            free(params->wasm_data);
            free(params);
            return ESP_ERR_NO_MEM;
        }
        
        ESP_LOGI(TAG, "Task WASM creata con successo (handle: %p)", 
                (void*)task_handle);
        return ESP_OK;
    
    } else {
        ESP_LOGE(TAG, "Errore nella lettura del file WASM: %s (codice: %d)", 
                esp_err_to_name(result), result);
        return result;
    }   

    return 0;  // Comando eseguito con successo
}

// Handler per il comando "echo"
static int cmd_echo(shell_t* shell, int argc, char** argv) {   
    for (int i = 0; i < argc; i++) {
        ESP_LOGI(TAG, "%s ", argv[i]);
    }
    ESP_LOGI(TAG, "\n");
    return 0;
}

// Handler per il comando "ls"
static int cmd_ls(shell_t* shell, int argc, char** argv) {
    if(argc > 0){
        //const char* path = argc > 0 ? argv[0] : ".";    
        //ESP_LOGI(TAG, "Listing directory: %s\n", path);

        ESP_LOGI(TAG, "ls: currently unmanaged arguments");
    }
    
    list_files(shell->cwd);

    return 0;
}

static int cmd_restart(shell_t* shell, int argc, char** argv){
    restart_device();
    return 0;
}

static int cmd_core_dump(shell_t* shell, int argc, char** argv){
    print_core_dump_info();
    return 0;
}

static int cmd_devinfo(shell_t* shell, int argc, char** argv){
    device_info();    
    return 0;
}

static int cmd_help(shell_t* shell, int argc, char **argv) {
    ESP_LOGI(TAG, "Comandi disponibili:");
    
    // Itera attraverso l'array dei comandi fino al terminatore
    const command_entry_t *cmd = &commands[0];
    while (cmd->command != NULL) {
        ESP_LOGI(TAG, "  - %s", cmd->command);
        cmd++;
    }
    
    return 0;
}

////
////
////

// Funzione principale per l'elaborazione dei comandi
int process_command(shell_t* shell, char* cmd_str) {
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

    /// Pop program
    char* program = argv[0];     // salva il primo argomento

    // sposta tutti gli elementi di una posizione indietro
    for(int i = 0; i < argc-1; i++) {
        argv[i] = argv[i+1];
    }

    argc--;     // decrementa il contatore degli argomenti
    /// 

    // Cerca il comando nella tabella
    for (const command_entry_t* cmd = commands; cmd->command != NULL; cmd++) {
        if (strcmp(program, cmd->command) == 0) {
            return cmd->handler(shell, argc, argv);
        }
    }
    
    ESP_LOGI(TAG, "Unknown command: %s\n", argv[0]);
    return -1;
}

///
/// Shell management
///

// Funzione per inizializzare la shell
shell_t* shell_init(shell_t* shell) {
    if(!shell)
        shell = malloc(sizeof(shell_t));
    
    if (!shell) return NULL;
    
    shell->cwd = strdup("/");  // Directory iniziale
    shell->variables = NULL;    // Lista variabili inizialmente vuota
    return shell;
}

// Funzione per aggiungere/modificare una variabile
int shell_set_variable(shell_t *shell, const char *name, const char *value) {
    if (!shell || !name || !value) return -1;

    // Cerca se la variabile esiste già
    variable_t *curr = shell->variables;
    while (curr) {
        if (strcmp(curr->name, name) == 0) {
            // Aggiorna il valore
            free(curr->value);
            curr->value = strdup(value);
            return 0;
        }
        curr = curr->next;
    }

    // Crea una nuova variabile
    variable_t *new_var = malloc(sizeof(variable_t));
    if (!new_var) return -1;

    new_var->name = strdup(name);
    new_var->value = strdup(value);
    new_var->next = shell->variables;
    shell->variables = new_var;

    return 0;
}

// Funzione per ottenere il valore di una variabile
char* shell_get_variable(shell_t *shell, const char *name) {
    if (!shell || !name) return NULL;

    variable_t *curr = shell->variables;
    while (curr) {
        if (strcmp(curr->name, name) == 0) {
            return curr->value;
        }
        curr = curr->next;
    }
    return NULL;
}

// Funzione per liberare la memoria
void shell_cleanup(shell_t *shell) {
    if (!shell) return;

    // Libera la memoria delle variabili
    variable_t *curr = shell->variables;
    while (curr) {
        variable_t *next = curr->next;
        free(curr->name);
        free(curr->value);
        free(curr);
        curr = next;
    }

    free((void*)shell->cwd);
    free(shell);
}