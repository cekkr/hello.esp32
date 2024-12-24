#ifndef HELLOESP_DEVICE_H
#define HELLOESP_DEVICE_H
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

void restart_device(void);
void disable_wdt_reg();
void reset_wdt();
void watchdog_task_register();
void handle_watchdog();
void print_ram_info(void);
void device_info(void);

#endif  // HELLOESP_DEVICE_H