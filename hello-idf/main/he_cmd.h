#ifndef HELLOESP_CMD
#define HELLOESP_CMD

#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <ctype.h>

#include "esp_log.h"

#include "he_device.h"
#include "he_defines.h"

#define MAX_ARGS 32

typedef struct shell {
    const char *cwd; // Current working directory
} shell_t;

typedef struct {
    const char* command;
    int (*handler)(shell_t* shell, int argc, char** argv);
} command_entry_t;

// Funzione di utilità per rimuovere gli spazi iniziali e finali
static char* trim(char* str);

// Parser degli argomenti che gestisce le stringhe tra virgolette
static int parse_arguments(char* input, char** argv);

////
////
////

static int cmd_run(shell_t* shell, int argc, char** argv);
static int cmd_echo(shell_t* shell, int argc, char** argv);
static int cmd_ls(shell_t* shell, int argc, char** argv);
static int cmd_restart(shell_t* shell, int argc, char** argv);
static int cmd_core_dump(shell_t* shell, int argc, char** argv);
static int cmd_devinfo(shell_t* shell, int argc, char** argv);
static int cmd_help(shell_t* shell, int argc, char **argv);

// Tabella dei comandi supportati
static const command_entry_t commands[] = {
    {"run", cmd_run},
    {"echo", cmd_echo},
    {"ls", cmd_ls},
    {"restart", cmd_restart},
    {"core_dump", cmd_core_dump},
    {"devinfo", cmd_devinfo},
    {"help", cmd_help},
    {NULL, NULL}  // Terminatore
};

// Funzione principale per l'elaborazione dei comandi
int process_command(shell_t* shell, char* cmd_str);

#endif