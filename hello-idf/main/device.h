#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"

void restart_device(void) {
    ESP_LOGI(TAG, "restart requested");
    
    // Esegue il riavvio del dispositivo
    esp_restart();
}

#endif  // HELLOESP_DEVICE_H