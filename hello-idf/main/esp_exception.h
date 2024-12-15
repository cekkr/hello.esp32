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

#endif // HELLOESP_ESP_EXCEPTION_H