#include "esp_system.h"
#include "esp_debug_helpers.h"

// Struttura per memorizzare il contesto dell'eccezione
typedef struct {
    uint32_t pc;      // Program Counter
    uint32_t ps;      // Processor State
    uint32_t a0;      // Return Address
    uint32_t a1;      // Stack Pointer
    uint32_t exc_cause; // Causa dell'eccezione
} exception_frame_t;

// Handler personalizzato per le eccezioni
void load_prohibited_handler(void *arg) {
    exception_frame_t *frame = (exception_frame_t *)arg;
    
    // Log dell'errore
    ESP_LOGE("Exception", "LoadProhibited error detected!");
    ESP_LOGE("Exception", "PC: 0x%08x", frame->pc);
    ESP_LOGE("Exception", "PS: 0x%08x", frame->ps);
    ESP_LOGE("Exception", "Cause: %d", frame->exc_cause);
    
    // Stampa dello stack trace
    esp_backtrace_print(10);
    
    // Qui puoi implementare la logica di recupero
    // Per esempio:
    // - Resettare variabili critiche
    // - Ripristinare lo stato precedente
    // - Salvare informazioni di debug
    
    // Opzionale: riavvio controllato del sistema
    // esp_restart();
    
    // Oppure continua l'esecuzione
    return;
}

// Funzione di inizializzazione da chiamare nel setup
void init_exception_handler(void) {
    ESP_ERROR_CHECK(esp_set_exception_handler(load_prohibited_handler));
}