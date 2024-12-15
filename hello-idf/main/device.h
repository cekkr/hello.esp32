#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"
#include "esp_task_wdt.h"
#include "soc/timer_group_struct.h"
#include "driver/timer.h"      
#include "soc/timer_group_reg.h"

#include "defines.h"

void restart_device(void) {
    ESP_LOGI(TAG, "restart requested");
    
    // Esegue il riavvio del dispositivo
    esp_restart();
}

#if ENABLE_WATCHDOG
void watchdog_task_register(){
    return;

    #if ENABLE_WATCHDOG
    esp_task_wdt_add(NULL);  // Registra il task corrente
    WATCHDOG_RESET;
    #endif
}

void handle_watchdog() {
    // 4. Disabilita Timer Group Watchdogs
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

    // 1. Disabilita RTC WDT
    #if ENABLE_WATCHDOG
    if(false){
        //rtc_wdt_protect_off();
        //rtc_wdt_disable();
        //rtc_wdt_protect_on();

        // 2. Disabilita Task WDT
        esp_task_wdt_deinit();

        // Configurazione del Task Watchdog
        esp_task_wdt_config_t twdt_config = {
            .timeout_ms = 60000,                // timeout di 3 secondi
            .idle_core_mask = (1 << 0),        // monitora il core 0
            .trigger_panic = false              // genera panic in caso di timeout
        };
        esp_task_wdt_init(&twdt_config);       
    }

     // Sottoscrivi il task corrente al watchdog
    esp_task_wdt_add(NULL);
    
    #endif   
}
#else
void watchdog_task_register(){}
void handle_watchdog() {
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
}
#endif

#endif  // HELLOESP_DEVICE_H