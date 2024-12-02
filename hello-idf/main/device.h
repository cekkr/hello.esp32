#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H

#include "esp_system.h"

void restart_device(void) {
    // Breve attesa prima del riavvio
    vTaskDelay(pdMS_TO_TICKS(100));
    
    // Esegue il riavvio del dispositivo
    esp_restart();
}

#endif  // HELLOESP_DEVICE_H