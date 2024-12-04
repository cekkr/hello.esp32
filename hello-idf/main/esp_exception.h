#ifndef HELLOESP_ESP_EXCEPTION_H
#define HELLOESP_ESP_EXCEPTION_H

#include "esp_system.h"
#include "esp_debug_helpers.h"
#include "esp_log.h"
#include "esp_event.h"

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

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
static void custom_panic_handler(void) {
    uint32_t error_code = 0xDEAD;
    ESP_ERROR_CHECK(esp_event_post(ERROR_EVENTS, ERROR_EVENT_PANIC, &error_code, sizeof(error_code), portMAX_DELAY));
}

// Inizializzazione del sistema di gestione errori
esp_err_t init_error_handling(void) {
    // Crea il loop di eventi di default se non esiste
    esp_err_t ret = esp_event_loop_create_default();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        return ret;
    }
    
    // Registra l'handler per gli eventi di errore
    ret = esp_event_handler_register_with(
        ESP_EVENT_ANY_BASE,    // Gestisce eventi da qualsiasi base
        ESP_EVENT_ANY_ID,      // Gestisce qualsiasi ID evento
        error_event_handler,    // La funzione handler
        NULL,                  // Argomenti extra (non necessari)
        NULL                   // Handle dell'evento (non necessario)
    );
    
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Errore nella registrazione dell'handler: %d", ret);
        return ret;
    }
    
    // Imposta il panic handler personalizzato
    esp_register_shutdown_handler(custom_panic_handler);
    
    ESP_LOGI(TAG, "Sistema di gestione errori inizializzato");
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

#endif // HELLOESP_ESP_EXCEPTION_H