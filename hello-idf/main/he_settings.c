
#include "he_settings.h"

#include "cJSON.h"

// Funzione per salvare le impostazioni in formato JSON
char* settings_save(const settings_t* settings) {
    // Creiamo l'oggetto JSON principale
    cJSON* root = cJSON_CreateObject();
    if (!root) {
        return NULL;
    }

    // Iteriamo attraverso tutti i campi della struttura usando la macro
    #define X(name, type, default) \
        if (sizeof(type) == sizeof(bool)) { \
            cJSON_AddBoolToObject(root, #name, settings->name); \
        }
    SETTINGS_FIELDS(X)
    #undef X

    // Convertiamo l'oggetto JSON in stringa
    char* json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    
    return json_str;
}

// Funzione per caricare le impostazioni da una stringa JSON
bool settings_load(const char* json_str, settings_t* settings) {
    // Partiamo dai valori predefiniti
    *settings = settings_default;
    
    // Verifichiamo che la stringa JSON non sia NULL
    if (!json_str) {
        return false;
    }

    // Parsifichiamo la stringa JSON
    cJSON* root = cJSON_Parse(json_str);
    if (!root) {
        return false;
    }

    // Iteriamo attraverso tutti i campi definiti nella struttura
    #define X(_name, _type, _default) \
    { \
        cJSON* field = cJSON_GetObjectItem(root, #_name); \
        if (field) { \
            /* Se il campo esiste nel JSON, verifichiamo che sia un booleano */ \
            if (field->type == cJSON_True || field->type == cJSON_False) { \
                settings->_name = (field->type == cJSON_True); \
            } \
        } else { \
            /* Se il campo non esiste nel JSON, usiamo il valore default */ \
            settings->_name = _default; \
        } \
    }

    cJSON_Delete(root);
    return true;
}