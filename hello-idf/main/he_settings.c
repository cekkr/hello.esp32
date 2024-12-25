
#include "he_settings.h"
#include "cJSON.h"

char* settings_save(const settings_t* settings) {
    cJSON* root = cJSON_CreateObject();
    if (!root) {
        return NULL;
    }

    // Modifichiamo la macro per saltare i campi che iniziano con underscore
    #define X(name, type, default) \
        /* Controlliamo se il nome inizia con underscore usando il preprocessore */ \
        if (#name[0] != '_') { \
            if (sizeof(type) == sizeof(bool)) { \
                cJSON_AddBoolToObject(root, #name, settings->name); \
            } \
        }
    SETTINGS_FIELDS(X)
    #undef X

    char* json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    
    return json_str;
}

bool settings_load(const char* json_str, settings_t* settings) {
    // Inizializziamo sempre tutti i campi con i valori default
    *settings = settings_default;
    
    if (!json_str) {
        return false;
    }

    cJSON* root = cJSON_Parse(json_str);
    if (!root) {
        return false;
    }

    // Modifichiamo la macro per processare solo i campi che non iniziano con underscore
    #define X(_name, _type, _default) \
        /* Processiamo solo i campi che non iniziano con underscore */ \
        if (#_name[0] != '_') { \
            cJSON* field = cJSON_GetObjectItem(root, #_name); \
            if (field) { \
                if (field->type == cJSON_True || field->type == cJSON_False) { \
                    settings->_name = (field->type == cJSON_True); \
                } \
            } else { \
                settings->_name = _default; \
            } \
        }
    SETTINGS_FIELDS(X)
    #undef X

    cJSON_Delete(root);
    return true;
}

////////////////////////////////////////////////////////////////

settings_field_t settings_get_field(settings_t* settings, const char* field_name) {
    settings_field_t result = {
        .type = SETTINGS_TYPE_UNKNOWN,
        .value = NULL,
        .found = false
    };

    // Macro helper che confronta il nome del campo e imposta il risultato
    #define X(_name, _type, _default) \
        if (#_name[0] != '_' && strcmp(field_name, #_name) == 0) { \
            result.found = true; \
            result.value = &settings->_name; \
            /* Determiniamo il tipo in base al tipo dichiarato nella macro */ \
            if (strcmp(#_type, "bool") == 0) { \
                result.type = SETTINGS_TYPE_BOOL; \
            } else if (strcmp(#_type, "int") == 0) { \
                result.type = SETTINGS_TYPE_INT; \
            } else if (strcmp(#_type, "float") == 0) { \
                result.type = SETTINGS_TYPE_FLOAT; \
            } else if (strcmp(#_type, "char*") == 0) { \
                result.type = SETTINGS_TYPE_STRING; \
            } \
        }
    
    // Applichiamo la macro a tutti i campi
    SETTINGS_FIELDS(X)
    #undef X

    return result;
}

settings_t settings;
settings_t* get_main_settings(){
    return &settings;
}