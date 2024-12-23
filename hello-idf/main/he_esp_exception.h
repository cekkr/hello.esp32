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
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "esp_private/panic_internal.h"
#include "esp_core_dump.h"
#include "esp_partition.h"

typedef struct log_mapping {
    const char* tag;
    const char* custom_description;
} log_mapping_t;

void print_core_dump_info();
esp_err_t init_error_handling(void);
void trigger_error_event(uint32_t error_code);
void init_custom_logging(void);
#endif // HELLOESP_ESP_EXCEPTION_H