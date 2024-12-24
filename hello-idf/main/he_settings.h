#pragma once

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SETTINGS_FIELDS(X) \
    X(disable_serial_monitor_during_run, bool, false)

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