#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"
#include "esp_task_wdt.h"
#include "soc/timer_group_struct.h"
#include "driver/timer.h"      
#include "soc/timer_group_reg.h"
#include "soc/rtc_cntl_reg.h"

#include "defines.h"

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
    if(true){
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
            .timeout_ms = 60000,                // timeout di 3 secondi
            .idle_core_mask = core_mask,        
            .trigger_panic = true              // genera panic in caso di timeout
        };
        esp_task_wdt_init(&twdt_config);       
    }

    reset_wdt(); 
    disable_wdt_reg();  

     // Sottoscrivi il task corrente al watchdog
    esp_task_wdt_add(NULL);

    #endif   
}
#else
void watchdog_task_register(){}
void handle_watchdog() {
    reset_wdt();
}
#endif

#endif  // HELLOESP_DEVICE_H