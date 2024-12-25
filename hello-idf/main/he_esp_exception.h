#ifndef HELLOESP_ESP_EXCEPTION_H
#define HELLOESP_ESP_EXCEPTION_H

#include "esp_err.h"

typedef struct log_mapping {
    const char* tag;
    const char* custom_description;
} log_mapping_t;

void print_core_dump_info();
esp_err_t init_error_handling(void);
void trigger_error_event(uint32_t error_code);
void init_custom_logging(void);

#endif // HELLOESP_ESP_EXCEPTION_H