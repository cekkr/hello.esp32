#ifndef HE_SETTINGS_H // pragma twice - ha ha
#define HE_SETTINGS_H

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

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
    X(_sd_card_initialized, bool, false) \
    X(_serial_writer_broker_connected, bool, false) \
    X(_exclusive_serial_mode, bool, false) \
    X(_disable_monitor, bool, false) \
    X(_serial_wasm_read, bool, false) \
    X(_serial_wasm_read_string, char*, false) \
    X(_serial_mutex, int, NULL)

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

extern settings_t settings;
settings_t* get_main_settings();

#endif