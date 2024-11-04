Ti aiuto a creare un esempio di codice per gestire un file pre-allocato su SD card in ESP-IDF con FreeRTOS.



```c
#include <stdio.h>
#include <string.h>
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/sdspi_host.h"
#include "esp_log.h"

#define MOUNT_POINT "/sdcard"
#define FILE_SIZE (32 * 1024)  // 32 KB

static const char *TAG = "sd_card";

void create_preallocated_file(void) {
    // Configurazione del bus SPI per la SD card
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    sdspi_slot_config_t slot_config = SDSPI_SLOT_CONFIG_DEFAULT();
    
    // Opzioni di mount per FATFS
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };

    sdmmc_card_t* card;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount(MOUNT_POINT, &host, &slot_config, &mount_config, &card);

    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Errore nel montaggio della SD card (%s)", esp_err_to_name(ret));
        return;
    }

    // Crea il percorso completo del file
    char filepath[64];
    snprintf(filepath, sizeof(filepath), MOUNT_POINT "/file_32k.bin");

    // Apre il file in modalità scrittura
    FILE* f = fopen(filepath, "wb");
    if (f == NULL) {
        ESP_LOGE(TAG, "Impossibile creare il file");
        esp_vfs_fat_sdmmc_unmount();
        return;
    }

    // Pre-alloca lo spazio sul file
    if (fseek(f, FILE_SIZE - 1, SEEK_SET) != 0) {
        ESP_LOGE(TAG, "Errore nel seek");
        fclose(f);
        esp_vfs_fat_sdmmc_unmount();
        return;
    }

    // Scrive un byte per allocare effettivamente lo spazio
    uint8_t endByte = 0;
    if (fwrite(&endByte, 1, 1, f) != 1) {
        ESP_LOGE(TAG, "Errore nella scrittura");
        fclose(f);
        esp_vfs_fat_sdmmc_unmount();
        return;
    }

    // Riavvolge il file all'inizio
    rewind(f);

    // Esempio: riempi il file con dati (opzionale)
    uint8_t buffer[1024] = {0};
    for (size_t i = 0; i < FILE_SIZE; i += sizeof(buffer)) {
        size_t write_size = (i + sizeof(buffer) > FILE_SIZE) ? (FILE_SIZE - i) : sizeof(buffer);
        if (fwrite(buffer, 1, write_size, f) != write_size) {
            ESP_LOGE(TAG, "Errore nella scrittura dei dati");
            break;
        }
    }

    // Chiude il file
    fclose(f);
    
    ESP_LOGI(TAG, "File creato con successo: %s", filepath);

    // Smonta la SD card
    esp_vfs_fat_sdmmc_unmount();
}

```

Questo codice fa diverse cose importanti:

1. Inizializza e monta la SD card usando il bus SPI
2. Crea un file di 32KB pre-allocato
3. Opzionalmente riempie il file con dati (in questo caso con zeri)
4. Gestisce gli errori in modo appropriato
5. Smonta correttamente la SD card alla fine

Per usare questo codice, dovrai:

1. Configurare correttamente i pin SPI nel tuo sdkconfig o tramite menuconfig
2. Includere i componenti necessari nel CMakeLists.txt del tuo progetto
3. Chiamare la funzione `create_preallocated_file()` da un task

Posso aiutarti con la configurazione dei pin specifici per il tuo hardware se ne hai bisogno.
