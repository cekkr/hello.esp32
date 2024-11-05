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
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mgt_string.h"

void init_sd_pins() {
    ESP_LOGI("hello_esp", "Initializing SD pins with pull-ups...\n");
    
    // Configura tutti i pin con pull-up
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT_OUTPUT,
        .pin_bit_mask = ((1ULL<<SD_SCK) | (1ULL<<SD_MOSI) | (1ULL<<SD_CS)),
        .pull_down_en = 0,
        .pull_up_en = 1
    };
    gpio_config(&io_conf);

    // MISO configurato separatamente
    gpio_config_t miso_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL<<SD_MISO),
        .pull_down_en = 0,
        .pull_up_en = 1
    };
    gpio_config(&miso_conf);

    // Imposta esplicitamente i pull-up
    gpio_set_pull_mode(SD_MISO, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_MOSI, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_SCK, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_CS, GPIO_PULLUP_ONLY);

    // Imposta CS alto (deselezionato)
    gpio_set_direction(SD_CS, GPIO_MODE_OUTPUT);
    gpio_set_level(SD_CS, 1);

    // Aspetta che le tensioni si stabilizzino
    vTaskDelay(pdMS_TO_TICKS(100));

    ESP_LOGI("hello_esp", "Testing SD pins state:\n");
    ESP_LOGI("hello_esp", "CS (GPIO%d) Level: %d\n", SD_CS, gpio_get_level(SD_CS));
    ESP_LOGI("hello_esp", "MISO (GPIO%d) Level: %d\n", SD_MISO, gpio_get_level(SD_MISO));
    ESP_LOGI("hello_esp", "MOSI (GPIO%d) Level: %d\n", SD_MOSI, gpio_get_level(SD_MOSI));
    ESP_LOGI("hello_esp", "SCK (GPIO%d) Level: %d\n", SD_SCK, gpio_get_level(SD_SCK));
    
    // Test di toggle dei pin per verificare il funzionamento
    ESP_LOGI("hello_esp", "\nTesting pin toggles:\n");
    for (int i = 0; i < 3; i++) {
        gpio_set_level(SD_CS, 0);
        gpio_set_level(SD_MOSI, 0);
        gpio_set_level(SD_SCK, 0);
        ESP_LOGI("hello_esp", "Pins Low - MISO: %d\n", gpio_get_level(SD_MISO));
        vTaskDelay(pdMS_TO_TICKS(100));
        
        gpio_set_level(SD_CS, 1);
        gpio_set_level(SD_MOSI, 1);
        gpio_set_level(SD_SCK, 1);
        ESP_LOGI("hello_esp", "Pins High - MISO: %d\n", gpio_get_level(SD_MISO));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    
    // Ritorna CS alto per inizializzazione
    gpio_set_level(SD_CS, 1);
    vTaskDelay(pdMS_TO_TICKS(100));
}

void init_sd_card() {
    esp_err_t ret;
    
    // Inizializza i pin
    init_sd_pins();
    
    ESP_LOGI("hello_esp", "\nInitializing SPI bus...\n");
    spi_bus_config_t bus_cfg = {
        .mosi_io_num = SD_MOSI,
        .miso_io_num = SD_MISO,
        .sclk_io_num = SD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4000,
        .flags = SPICOMMON_BUSFLAG_MASTER,
    };

    // Inizializza il bus SPI con frequenza molto bassa
    ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CHAN);
    if (ret != ESP_OK) {
        ESP_LOGI("hello_esp", "Failed to initialize bus. Error: %s\n", esp_err_to_name(ret));
        //return;
    }

    ESP_LOGI("hello_esp", "SPI bus initialized successfully\n");

    // Configurazione host con frequenza molto bassa per il debug
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SPI2_HOST;
    host.max_freq_khz = 400; // Ridotto a 400KHz per il debug

    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs = SD_CS;
    slot_config.host_id = host.slot;

    ESP_LOGI("hello_esp", "\nMounting SD card...\n");
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };

    sdmmc_card_t *card;
    ret = esp_vfs_fat_sdspi_mount(MOUNT_POINT, &host, &slot_config, &mount_config, &card);

    if (ret != ESP_OK) {
        ESP_LOGI("hello_esp", "\nMount failed with error: %s (0x%x)\n", esp_err_to_name(ret), ret);
        ESP_LOGI("hello_esp", "Debug info:\n");
        ESP_LOGI("hello_esp", "1. Check physical connections:\n");
        ESP_LOGI("hello_esp", "   - CS   -> GPIO%d\n", SD_CS);
        ESP_LOGI("hello_esp", "   - MISO -> GPIO%d\n", SD_MISO);
        ESP_LOGI("hello_esp", "   - MOSI -> GPIO%d\n", SD_MOSI);
        ESP_LOGI("hello_esp", "   - SCK  -> GPIO%d\n", SD_SCK);
        ESP_LOGI("hello_esp", "2. Verify SD card is properly inserted\n");
        ESP_LOGI("hello_esp", "3. Check if card works in a computer\n");
        ESP_LOGI("hello_esp", "4. Verify 3.3V power supply\n");
        ESP_LOGI("hello_esp", "5. Add 10kΩ pull-up resistors if not present\n");
        return;
    }

    ESP_LOGI("hello_esp", "\nSD card mounted successfully!\n");
    ESP_LOGI("hello_esp", "Card info:\n");
    ESP_LOGI("hello_esp", "Name: %s\n", card->cid.name);
    ESP_LOGI("hello_esp", "Type: %s\n", (card->ocr & (1 << 30)) ? "SDHC/SDXC" : "SDSC");
    ESP_LOGI("hello_esp", "Speed: %s\n", (card->csd.tr_speed > 25000000) ? "High Speed" : "Default Speed");
    ESP_LOGI("hello_esp", "Size: %lluMB\n", ((uint64_t)card->csd.capacity) * card->csd.sector_size / (1024 * 1024));
}

void mostra_info_sd(const char* mount_point) {    
    ESP_LOGI("hello_esp", "\nInizio lettura info sd in %s:\n", mount_point);

    FATFS* fs;
    size_t total_bytes;
    size_t free_bytes;
    esp_err_t ret = esp_vfs_fat_info(mount_point, &total_bytes, &free_bytes);
    if (ret != ESP_OK) {
        ESP_LOGE("hello_esp", "esp_vfs_fat_info err: %s\n", esp_err_to_name(ret));
        return;
    }

    ESP_LOGI("hello_esp", "f_getfree\n");
    DWORD fre_clust;
    FRESULT res = f_getfree(mount_point, &fre_clust, &fs);
    if (res != FR_OK) {
        // Handle error
        return;
    }

    ESP_LOGI("hello_esp", "f_getfree return\n");

    // Calculate total and free space
    size_t total_sectors = (fs->n_fatent - 2) * fs->csize;
    size_t free_sectors = fre_clust * fs->csize;

    // Sector size is typically 512 bytes
    // fs->ssize contiene il sector size in bytes
    size_t sector_size = fs->ssize;
    total_bytes = total_sectors * sector_size;
    free_bytes = free_sectors * sector_size;
    
    // Converte in megabytes per leggibilità
    double total_mb = total_bytes / (1024.0 * 1024.0);
    double free_mb = free_bytes / (1024.0 * 1024.0);
    double used_mb = total_mb - free_mb;
    
    ESP_LOGI("hello_esp", "\nInformazioni SD Card montata in %s:\n", mount_point);
    ESP_LOGI("hello_esp", "----------------------------------------\n");
    ESP_LOGI("hello_esp", "Dimensione blocco (chunk size): %d bytes\n", sector_size);
    ESP_LOGI("hello_esp", "Spazio totale: %.2f MB\n", total_mb);
    ESP_LOGI("hello_esp", "Spazio utilizzato: %.2f MB\n", used_mb);
    ESP_LOGI("hello_esp", "Spazio libero: %.2f MB\n", free_mb);
    ESP_LOGI("hello_esp", "Percentuale utilizzata: %.1f%%\n", (used_mb / total_mb) * 100);
    ESP_LOGI("hello_esp", "----------------------------------------\n");


    char* text = string_printf("hello_esp", "Chunk size: %d", sector_size);
    LCD_ShowString(10,40,WHITE,BLACK,12,text,0);
}

