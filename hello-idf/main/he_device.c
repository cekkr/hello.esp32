#include "esp_system.h"
#include "esp_task_wdt.h"
#include "soc/timer_group_struct.h"
#include "driver/timer.h"      
#include "soc/timer_group_reg.h"
#include "soc/rtc_cntl_reg.h"
#include <stdio.h>
#include "esp_log.h"
#include "esp_chip_info.h"
#include "esp_flash_spi_init.h"
#include "esp_heap_caps.h"
//#include "esp_spi_flash.h"
#include "he_defines.h"

#include "he_device.h"

void restart_device(void) {
    ESP_LOGI(TAG, "Restarting device...");
    
    vTaskDelay(pdMS_TO_TICKS(1000));

    // Esegue il riavvio del dispositivo
    esp_restart();
}

void disable_wdt_reg(){
    WRITE_PERI_REG(RTC_CNTL_WDTCONFIG0_REG, 0);   // Disabilita RTC WDT 
    WRITE_PERI_REG(RTC_CNTL_WDTWPROTECT_REG, 0);  // Rimuovi protezione scrittura 
}

void reset_wdt(){
    // https://gitlab.informatik.uni-bremen.de/fbrning/esp-idf/-/blob/master/components/soc/esp32s3/include/soc/timer_group_struct.h
    TIMERG0.wdtwprotect.wdt_wkey = TIMG_WDT_WKEY_V;
    TIMERG0.wdtfeed.val = 1;
    TIMERG0.wdtconfig0.wdt_en = 0;
    TIMERG0.wdtconfig0.wdt_stg0 = RTC_WDT_STG_SEL_OFF;
    TIMERG0.wdtconfig0.wdt_stg1 = RTC_WDT_STG_SEL_OFF;
    TIMERG0.wdtconfig0.wdt_stg2 = RTC_WDT_STG_SEL_OFF;
    TIMERG0.wdtconfig0.wdt_stg3 = RTC_WDT_STG_SEL_OFF;
    TIMERG0.wdtwprotect.val = 0;

    TIMERG1.wdtwprotect.wdt_wkey = TIMG_WDT_WKEY_V;
    TIMERG1.wdtfeed.val = 1;
    TIMERG1.wdtconfig0.wdt_en = 0;
    TIMERG1.wdtconfig0.wdt_stg0 = RTC_WDT_STG_SEL_OFF;
    TIMERG1.wdtconfig0.wdt_stg1 = RTC_WDT_STG_SEL_OFF;
    TIMERG1.wdtconfig0.wdt_stg2 = RTC_WDT_STG_SEL_OFF;
    TIMERG1.wdtconfig0.wdt_stg3 = RTC_WDT_STG_SEL_OFF;
    TIMERG1.wdtwprotect.val = 0; 

    #if !ENABLE_WATCHDOG
    disable_wdt_reg();  
    #endif    
}

#if ENABLE_WATCHDOG
void watchdog_task_register(){
    return;

    #if ENABLE_WATCHDOG
    // Registra il task corrente
    WATCHDOG_RESET;
    #endif
}

void handle_watchdog() {
    // 4. Disabilita Timer Group Watchdogs
    // https://gitlab.informatik.uni-bremen.de/fbrning/esp-idf/-/blob/master/components/soc/esp32s3/include/soc/timer_group_struct.h        

    // 1. Disabilita RTC WDT
    #if ENABLE_WATCHDOG
    if(false){
        //rtc_wdt_protect_off();
        //rtc_wdt_disable();
        //rtc_wdt_protect_on();

        // 2. Disabilita Task WDT
        //esp_task_wdt_deinit();

        // Configurazione del Task Watchdog
        bool enableCore0 = true;
        bool enableCore1 = true;
        uint32_t core_mask = 0;

        if(enableCore0) core_mask |= (1 << 0);
        if(enableCore1) core_mask |= (1 << 1);

        esp_task_wdt_config_t twdt_config = {
            .timeout_ms = 5000,                // timeout di 3 secondi
            .idle_core_mask = core_mask,        
            .trigger_panic = true              // genera panic in caso di timeout
        };
        esp_task_wdt_init(&twdt_config);       
    }

    reset_wdt(); 
    //disable_wdt_reg();  

    #endif   
}
#else
void watchdog_task_register(){}
void handle_watchdog() {
    reset_wdt();
}
#endif

///
/// Infos
///

void print_executable_memory_ranges() {
    ESP_LOGI(TAG, "Executable memory dump (includes addresses):");
    heap_caps_dump(MALLOC_CAP_EXEC);
}

// Ottiene la dimensione totale della memoria eseguibile
size_t get_total_executable_size(void) {
    multi_heap_info_t info;
    heap_caps_get_info(&info, MALLOC_CAP_EXEC);
    return info.total_allocated_bytes + info.total_free_bytes;
}

// Ottiene lo spazio libero nella memoria eseguibile
size_t get_free_executable_size(void) {
    return heap_caps_get_free_size(MALLOC_CAP_EXEC);
}

// Ottiene la dimensione del blocco libero più grande
size_t get_largest_free_executable_block(void) {
    return heap_caps_get_largest_free_block(MALLOC_CAP_EXEC);
}

// Ottiene il minimo spazio libero registrato (watermark)
size_t get_min_free_executable_size(void) {
    return heap_caps_get_minimum_free_size(MALLOC_CAP_EXEC);
}

// Stampa tutte le informazioni sulla memoria eseguibile
void print_executable_memory_info(void) {
    ESP_LOGI(TAG, "Executable Memory Information:");
    ESP_LOGI(TAG, "Total size: %d bytes", get_total_executable_size());
    ESP_LOGI(TAG, "Free size: %d bytes", get_free_executable_size());
    ESP_LOGI(TAG, "Largest free block: %d bytes", get_largest_free_executable_block());
    ESP_LOGI(TAG, "Minimum free size ever: %d bytes", get_min_free_executable_size());
    
    // Stampa informazioni dettagliate usando l'API integrata
    ESP_LOGI(TAG, "\nDetailed heap info:");
    heap_caps_print_heap_info(MALLOC_CAP_EXEC);

    ESP_LOGI(TAG, "\nExecutable Memory Ranges:");
    print_executable_memory_ranges();
}

///
///
///

// Informazioni sulla CPU e sul chip
void print_chip_info(void) {
    esp_chip_info_t chip_info;
    esp_chip_info(&chip_info);
    
    ESP_LOGI(TAG, "Chip Info:");
    ESP_LOGI(TAG, "- Model: %s", CONFIG_IDF_TARGET);
    ESP_LOGI(TAG, "- Cores: %d", chip_info.cores);
    ESP_LOGI(TAG, "- Feature: %s%s%s%s%s",
        (chip_info.features & CHIP_FEATURE_WIFI_BGN) ? "WiFi " : "",
        (chip_info.features & CHIP_FEATURE_BT) ? "BT " : "",
        (chip_info.features & CHIP_FEATURE_BLE) ? "BLE " : "",
        (chip_info.features & CHIP_FEATURE_EMB_FLASH) ? "Flash " : "",
        (chip_info.features & CHIP_FEATURE_EMB_PSRAM) ? "PSRAM " : "");
    ESP_LOGI(TAG, "- Revision number: %d", chip_info.revision);
}

// Informazioni sulla memoria Flash
void print_flash_info(void) {
    uint32_t flash_size;
    esp_flash_get_size(NULL, &flash_size);
    
    ESP_LOGI(TAG, "Flash Memory:");
    ESP_LOGI(TAG, "- Size: %lu MB", flash_size / (1024 * 1024));
    //ESP_LOGI(TAG, "- Speed: %u MHz", ESP_FLASH_SPEED / 1000000); // don't know where to include it
    /*ESP_LOGI(TAG, "- Mode: %s", 
        (ESP_FLASH_MODE == 0) ? "QIO" :
        (ESP_FLASH_MODE == 1) ? "QOUT" :
        (ESP_FLASH_MODE == 2) ? "DIO" :
        (ESP_FLASH_MODE == 3) ? "DOUT" : "Unknown");*/
}

// Informazioni sulla memoria RAM
void print_ram_info(void) {
    ESP_LOGI(TAG, "RAM Info:");
    ESP_LOGI(TAG, "- Total heap size: %lu bytes", esp_get_free_heap_size());
    ESP_LOGI(TAG, "- Minimum free heap size: %lu bytes", esp_get_minimum_free_heap_size());
    
    multi_heap_info_t info;
    heap_caps_get_info(&info, MALLOC_CAP_INTERNAL);
    ESP_LOGI(TAG, "Internal RAM:");
    ESP_LOGI(TAG, "- Total free bytes: %lu", info.total_free_bytes);
    ESP_LOGI(TAG, "- Total allocated bytes: %lu", info.total_allocated_bytes);
    ESP_LOGI(TAG, "- Largest free block: %lu", info.largest_free_block);
}

// Informazioni sulla PSRAM (se disponibile)
void print_psram_info(void) {
    #if ENABLE_SPIRAM
    ESP_LOGI(TAG, "PSRAM Info:");
    if (esp_psram_is_initialized()) {
        size_t psram_size = esp_psram_get_size();
        size_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        
        ESP_LOGI(TAG, "- PSRAM initialized");
        ESP_LOGI(TAG, "- Total size: %lu MB", psram_size / (1024 * 1024));
        ESP_LOGI(TAG, "- Free size: %lu bytes", free_psram);
        ESP_LOGI(TAG, "- Used size: %lu bytes", psram_size - free_psram);
    } else {
        ESP_LOGI(TAG, "- PSRAM not initialized or not available");
    }
    #endif
}

// Funzione principale che raccoglie tutte le informazioni
void device_info(void) {
    ESP_LOGI(TAG, "\n=== ESP32 Device Information ===\n");
    print_chip_info();
    ESP_LOGI(TAG, "");
    print_flash_info();
    ESP_LOGI(TAG, "");
    print_ram_info();
    ESP_LOGI(TAG, "");
    print_psram_info();
    ESP_LOGI(TAG, "");
    print_executable_memory_info();
    ESP_LOGI(TAG, "\n==============================\n");
}
