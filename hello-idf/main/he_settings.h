#pragma once

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Definiamo prima un enum per i possibili tipi che possiamo gestire
typedef enum {
    SETTINGS_TYPE_BOOL,
    SETTINGS_TYPE_INT,
    SETTINGS_TYPE_FLOAT,
    SETTINGS_TYPE_STRING,
    SETTINGS_TYPE_UNKNOWN
} settings_type_t;

// Struttura che conterrà il risultato della ricerca del campo
typedef struct {
    settings_type_t type;  // Tipo del campo trovato
    void* value;          // Puntatore al valore
    bool found;           // Indica se il campo è stato trovato
} settings_field_t;

////////////////////////////////////////////////////////////////////////

#define SETTINGS_FIELDS(X) \
    X(disable_serial_monitor_during_run, bool, false) \
    X(_sd_card_initialized, bool, false)

typedef struct settings {
    #define X(_name, _type, _default) _type _name;
    SETTINGS_FIELDS(X)
    #undef X
} settings_t;

static const char* settings_fields[] = {
    #define X(_name, _type, _default) #_name,
    SETTINGS_FIELDS(X)
    #undef X
};

static const settings_t settings_default = {
    #define X(_name, _type, _default) ._name = _default,
    SETTINGS_FIELDS(X)
    #undef X
};

char* settings_save(const settings_t* settings);
bool settings_load(const char* json_str, settings_t* settings);