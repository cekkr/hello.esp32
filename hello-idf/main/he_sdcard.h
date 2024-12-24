#ifndef HELLOESP_SDCARD_H
#define HELLOESP_SDCARD_H
#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include "esp_system.h"
#include "driver/gpio.h"
#include "esp_vfs.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/sdmmc_types.h"
#include "driver/sdspi_host.h"
#include "driver/gpio.h"
#include "driver/spi_common.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "he_defines.h"
#include "he_mgt_string.h"

void init_sd_pins();
void init_sd_card();
void mostra_info_sd(const char* mount_point);
#endif