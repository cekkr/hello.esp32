#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"
#include "esp_task_wdt.h"
#include "soc/timer_group_struct.h"
#include "driver/timer.h"
#include "soc/timer_group_reg.h"

void restart_device(void) {
    ESP_LOGI(TAG, "restart requested");
    
    // Esegue il riavvio del dispositivo
    esp_restart();
}

#define ENABLE_WATCHDOG 0

#if ENABLE_WATCHDOG
void watchdog_task_register(){
    return;
    esp_task_wdt_add(NULL);  // Registra il task corrente
    esp_task_wdt_reset(); 
}

void disable_watchdog() {
// 1. Disabilita RTC WDT
    rtc_wdt_protect_off();
    rtc_wdt_disable();
    rtc_wdt_protect_on();

    // 2. Disabilita Task WDT
    esp_task_wdt_deinit();

    // 3. Disabilita Interrupt WDT
    #if CONFIG_ESP_INT_WDT
        esp_int_wdt_stop();
    #endif

    // 4. Disabilita Timer Group Watchdogs
    // https://gitlab.informatik.uni-bremen.de/fbrning/esp-idf/-/blob/master/components/soc/esp32s3/include/soc/timer_group_struct.h
    TIMERG0.wdtwprotect.wdt_wkey = TIMG_WDT_WKEY_V;
    TIMERG0.wdtconfig0.wdt_en = 0; 
    TIMERG0.wdtwprotect.val = 0;
    
    TIMERG1.wdtwprotect.wdt_wkey = TIMG_WDT_WKEY_V;
    TIMERG1.wdtconfig0.wdt_en = 0;
    TIMERG1.wdtwprotect.val = 0;
}
#else
void watchdog_task_register(){}
void disable_watchdog() {}
#endif

#endif  // HELLOESP_DEVICE_H