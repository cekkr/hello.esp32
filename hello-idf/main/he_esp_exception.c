#include "esp_system.h"
#include "esp_debug_helpers.h"
#include "esp_log.h"
#include "esp_err.h"
#include "esp_debug_helpers.h"
#include "esp_private/panic_internal.h"
#include "esp_core_dump.h"
#include "esp_debug_helpers.h"
#include "esp_timer.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "esp_debug_helpers.h"
#include "esp_log.h"
#include "esp_event.h"

#include "he_esp_exception.h"
#include "he_defines.h"

#define ENABLE_COREDUMP 0

void print_core_dump_info() {
    #if ENABLE_COREDUMP
    printf( "================================================================");
    printf( "================================================================\n");

    esp_err_t err;
    
    const esp_partition_t *core_dump_partition = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_COREDUMP, NULL);
    if (core_dump_partition == NULL) {
        ESP_LOGW(TAG, "Core dump partition not found");
        return;
    }

    printf( "Core dump partition found: size=%d, addr=0x%x", 
             core_dump_partition->size, core_dump_partition->address);
    
    // Read first few bytes to check if partition is blank
    uint8_t buf[4];
    err = esp_partition_read(core_dump_partition, 0, buf, sizeof(buf));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read core dump partition: %s", esp_err_to_name(err));
        return;
    }
    
    // Check if partition is blank (all 0xFF)
    bool is_blank = true;
    for (int i = 0; i < sizeof(buf); i++) {
        if (buf[i] != 0xFF) {
            is_blank = false;
            break;
        }
    }
    
    if (is_blank) {
        ESP_LOGW(TAG, "Core dump partition is blank - no crash data available");
        return;
    }
    
    if (!esp_core_dump_image_check()) {
        ESP_LOGW(TAG, "No valid core dump found in flash");
        return;
    }

    printf( "Valid core dump found, processing...");

    esp_core_dump_summary_t *summary = malloc(sizeof(esp_core_dump_summary_t));
    if (summary == NULL) {
        ESP_LOGE(TAG, "Failed to allocate memory for core dump summary");
        return;
    }

    err = esp_core_dump_get_summary(summary);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get core dump summary: %s", esp_err_to_name(err));
        free(summary);
        return;
    }

    // Print basic crash information
    printf( "\nCore dump details:");
    printf( "Crashed task: %s", summary->exc_task);
    printf( "Task TCB: 0x%x", summary->exc_tcb);
    printf( "Exception PC: 0x%x", summary->exc_pc);
    printf( "Core dump version: %lu", summary->core_dump_version);
    
    // Print exception info
    printf( "\nException details:");
    printf( "Cause: 0x%x", summary->ex_info.exc_cause);
    printf( "Virtual address: 0x%x", summary->ex_info.exc_vaddr);
    
    // Print registers
    printf( "\nRegister dump:");
    for (int i = 0; i < 16; i++) {
        printf( "A%d: 0x%08x", i, summary->ex_info.exc_a[i]);
    }
    
    // Print EPC registers if available
    printf( "\nEPC registers:");
    for (int i = 0; i < EPCx_REGISTER_COUNT; i++) {
        if (summary->ex_info.epcx_reg_bits & (1 << i)) {
            printf( " EPC%d: 0x%08x ", i+1, summary->ex_info.epcx[i]);
        }
    }

    // Print backtrace
    if(summary->exc_bt_info.corrupted) printf("\nBacktrace corrupted up to %d", summary->exc_bt_info.depth);
    printf("\nBacktrace:"); // summary->exc_bt_info.corrupted ? "(corrupted)" : ""
    for (size_t i = 0; i < 16; i++) { // i < summary->exc_bt_info.depth &&
        printf(" 0x%08x:0x%08x", summary->exc_bt_info.bt[i], 
               i + 1 < summary->exc_bt_info.depth ? summary->exc_bt_info.bt[i + 1] : 0);
    }
    printf("\n");

    // Print SHA256 of the app
    printf( "\nApp ELF SHA256: ");
    for(int i = 0; i < APP_ELF_SHA256_SZ; i++) {
        printf("%02x", summary->app_elf_sha256[i]);
    }
    printf("\n");

    free(summary);
    printf(TAG, "\nCore dump analysis complete");

    printf(TAG, "================================================================");
    printf(TAG, "================================================================\n");
    #endif
}

///
///
///

// Definizione degli eventi personalizzati per errori
ESP_EVENT_DEFINE_BASE(ERROR_EVENTS);
enum {
    ERROR_EVENT_PANIC,
    ERROR_EVENT_EXCEPTION
};

// Handler per gli eventi di errore
static void error_event_handler(void* handler_args, esp_event_base_t base, int32_t id, void* event_data) {
    ESP_LOGW(TAG, "error_event_handler called");   

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
        
        default:
            esp_backtrace_print(10);
    }

    vTaskDelay(pdMS_TO_TICKS(1000));
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
    // Print last error message
    print_core_dump_info();    

    // Register error handler
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

    printf( "Error handling system initialized");
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

// Array di mappature messaggi-descrizioni
static const log_mapping_t log_mappings[] = {
    {"task_wdt", "add_entry(192): task is already subscribed", "Il task è già registrato nel watchdog timer"},
    // Aggiungi altre mappature qui
};

// Handler personalizzato per i log
static void custom_log_handler(esp_log_level_t level, const char* tag, const char* fmt, va_list args) {
    ESP_LOGI(TAG, "custom_log_handler called");

    char buffer[512];  // Assicurati che sia abbastanza grande
    vsnprintf(buffer, sizeof(buffer), fmt, args);

    if(level == ESP_LOG_ERROR) ESP_LOGE(TAG, "%s", buffer);
    if(level == ESP_LOG_WARN) ESP_LOGW(TAG, "%s", buffer);
    if(level == ESP_LOG_INFO) ESP_LOGI(TAG, "%s", buffer);
    if(level == ESP_LOG_DEBUG) ESP_LOGD(TAG, "%s", buffer);
    if(level == ESP_LOG_VERBOSE) ESP_LOGV(TAG, "%s", buffer);

    vTaskDelay(pdMS_TO_TICKS(100));
    return;

    // Se non viene trovata una mappatura, stampa il messaggio originale
    printf("%c (%d) %s: %s\n",
            log_level_to_char(level),
            get_log_timestamp(),
            tag,
            buffer);

    if(level == ESP_LOG_ERROR)
        esp_backtrace_print(10);   
}

// Funzione di inizializzazione
void init_custom_logging(void) {
    // Imposta il livello minimo di log
    //esp_log_level_set("*", ESP_LOG_INFO);  // ESP_LOG_NONE ESP_LOG_INFO    

    // Registra l'handler personalizzato
    //esp_log_set_vprintf(custom_log_handler); // uncomment to make this work
}