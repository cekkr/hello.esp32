#ifndef HELLOESP_IO
#define HELLOESP_IO

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_log.h"
#include "esp_err.h"

/**
 * @brief Legge un file e lo carica in memoria
 * @param file_path Path del file da leggere
 * @param out_data Puntatore al buffer dove verrà salvato il contenuto (verrà allocato dalla funzione)
 * @param out_size Puntatore dove verrà salvata la dimensione del file letto
 * @return ESP_OK in caso di successo, altrimenti un codice di errore
 */
esp_err_t read_file_to_memory(const char* file_path, uint8_t** out_data, size_t* out_size) {
    FILE* file = NULL;
    uint8_t* buffer = NULL;
    
    if (file_path == NULL || out_data == NULL || out_size == NULL) {
        ESP_LOGE(TAG, "Invalid input parameters");
        return ESP_ERR_INVALID_ARG;
    }

    // Apre il file in modalità lettura binaria
    file = fopen(file_path, "rb");
    if (file == NULL) {
        ESP_LOGE(TAG, "Failed to open file : %s", file_path);
        return ESP_ERR_NOT_FOUND;
    }

    // Ottiene la dimensione del file
    fseek(file, 0, SEEK_END);
    *out_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    // Alloca il buffer per contenere il file
    buffer = (uint8_t*)malloc(*out_size + 1);  // +1 per il terminatore null
    if (buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate memory");
        fclose(file);
        return ESP_ERR_NO_MEM;
    }

    // Legge il contenuto del file
    size_t bytes_read = fread(buffer, 1, *out_size, file);
    if (bytes_read != *out_size) {
        ESP_LOGE(TAG, "Failed to read file");
        free(buffer);
        fclose(file);
        return ESP_FAIL;
    }

    // Aggiunge il terminatore null alla fine
    buffer[*out_size] = '\0';
    
    // Chiude il file
    fclose(file);

    // Assegna il buffer al puntatore di output
    *out_data = buffer;

    ESP_LOGI(TAG, "File read successfully: %d bytes", *out_size);
    return ESP_OK;
}

#endif  // HELLOESP_IO