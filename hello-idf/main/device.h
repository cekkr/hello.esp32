#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"

void restart_device(void) {
    ESP_LOGI(TAG, "restart requested");
    
    // Esegue il riavvio del dispositivo
    esp_restart();
}

void watchdog_task_register(){
    return;
    esp_task_wdt_add(NULL);  // Registra il task corrente
    esp_task_wdt_reset(); 
}

#endif  // HELLOESP_DEVICE_H