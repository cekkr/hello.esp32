#ifndef HELLOESP_ESP_EXCEPTION_H
#define HELLOESP_ESP_EXCEPTION_H

#include "esp_system.h"
#include "esp_debug_helpers.h"
#include "esp_log.h"
#include "esp_event.h"

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_debug_helpers.h"
#include "esp_private/panic_internal.h"

#include "esp_log.h"
#include "esp_timer.h"


// Definizione degli eventi personalizzati per errori
ESP_EVENT_DEFINE_BASE(ERROR_EVENTS);
enum {
    ERROR_EVENT_PANIC,
    ERROR_EVENT_EXCEPTION
};

// Handler per gli eventi di errore
static void error_event_handler(void* handler_args, esp_event_base_t base, int32_t id, void* event_data) {
    switch (id) {
        case ERROR_EVENT_PANIC:
            ESP_LOGE(TAG, "Sistema in panic!");
            // Log dello stack trace
            esp_backtrace_print(10);
            
            // Qui puoi implementare la logica di recupero
            // Per esempio: salvare dati critici in flash
            
            // Riavvia il sistema dopo un breve delay
            vTaskDelay(pdMS_TO_TICKS(1000));
            esp_restart();
            break;
            
        case ERROR_EVENT_EXCEPTION:
            ESP_LOGE(TAG, "Eccezione rilevata!");
            // Gestione specifica per le eccezioni
            if (event_data != NULL) {
                uint32_t *error_data = (uint32_t*)event_data;
                ESP_LOGE(TAG, "Codice errore: %lu", *error_data);
            }
            break;
    }
}

// Funzione di panic handler personalizzata
static void custom_panic_handler(void* frame, panic_info_t* info) {
    ESP_LOGE(TAG, "Custom panic handler");
    esp_backtrace_print(100);
}

static void custom_shutdown_handler(void){
    ESP_LOGE(TAG, "Called shutdown handler");
    esp_backtrace_print(100);
}

// Inizializzazione del sistema di gestione errori
esp_err_t init_error_handling(void) {
    esp_register_shutdown_handler(custom_shutdown_handler);

    // Prima creiamo e verifichiamo l'event loop
    esp_err_t ret = esp_event_loop_create_default();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "Failed to create event loop: %d", ret);
        return ret;
    }

    // Attendiamo un po' per assicurarci che l'event loop sia pronto
    vTaskDelay(pdMS_TO_TICKS(100));

    // Ora registriamo l'handler
    ret = esp_event_handler_instance_register(
        ERROR_EVENTS,          // Event base
        ESP_EVENT_ANY_ID,      // Event ID
        error_event_handler,   // Event handler
        NULL,                  // Handler argument
        NULL                   // Handler instance (optional)
    );
    
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to register event handler: %d", ret);
        return ret;
    }

    //esp_set_panic_handler(custom_panic_handler);

    ESP_LOGI(TAG, "Error handling system initialized");
    return ESP_OK;
}

// Esempio di come inviare un evento di errore manualmente
void trigger_error_event(uint32_t error_code) {
    esp_err_t ret = esp_event_post(
        ERROR_EVENTS,
        ERROR_EVENT_EXCEPTION,
        &error_code,
        sizeof(error_code),
        portMAX_DELAY
    );
    
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Impossibile inviare l'evento di errore: %d", ret);
    }
}

////
////
////

// Funzione per ottenere il timestamp in millisecondi
static uint32_t get_log_timestamp(void) {
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

// Funzione per convertire il livello di log in carattere
static char log_level_to_char(esp_log_level_t level) {
    switch (level) {
        case ESP_LOG_ERROR:    return 'E';
        case ESP_LOG_WARN:     return 'W';
        case ESP_LOG_INFO:     return 'I';
        case ESP_LOG_DEBUG:    return 'D';
        case ESP_LOG_VERBOSE:  return 'V';
        default:              return '?';
    }
}

// Struttura per memorizzare informazioni aggiuntive sui messaggi
typedef struct {
    const char* tag;
    const char* custom_description;
} log_mapping_t;

// Array di mappature messaggi-descrizioni
static const log_mapping_t log_mappings[] = {
    {"task_wdt", "add_entry(192): task is already subscribed", "Il task è già registrato nel watchdog timer"},
    // Aggiungi altre mappature qui
};

// Handler personalizzato per i log
static void custom_log_handler(esp_log_level_t level, const char* tag, const char* fmt, va_list args) {
    char buffer[512];
    vsnprintf(buffer, sizeof(buffer), fmt, args);

    // Cerca una mappatura corrispondente
    for (int i = 0; i < sizeof(log_mappings) / sizeof(log_mapping_t); i++) {
        if (strcmp(tag, log_mappings[i].tag) == 0 && 
            strstr(buffer, log_mappings[i].custom_description) != NULL) {
            // Stampa il messaggio originale con la descrizione personalizzata
            printf("%c (%d) %s: %s\nDescrizione: %s\n",
                   log_level_to_char(level),
                   get_log_timestamp(),
                   tag,
                   buffer,
                   log_mappings[i].custom_description);
            return;
        }
    }

    // Se non viene trovata una mappatura, stampa il messaggio originale
    printf("%c (%d) %s: %s\n",
            log_level_to_char(level),
            get_log_timestamp(),
            tag,
            buffer);

    esp_backtrace_print(10);
}

// Funzione di inizializzazione
void init_custom_logging(void) {
    // Imposta il livello minimo di log
    esp_log_level_set("*", ESP_LOG_INFO);
    
    // Registra l'handler personalizzato
    esp_log_set_vprintf(custom_log_handler);
}

#endif // HELLOESP_ESP_EXCEPTION_H