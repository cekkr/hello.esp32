#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_vfs.h"
#include "esp_log.h"
#include "esp_err.h"
#include "esp_rom_sys.h"
#include "soc/soc.h"
#include "esp_rom_sys.h"
#include "esp_log.h"

#include "he_defines.h"

#include "he_io.h"
//#include <sys/dirent.h>

const bool HE_DEBUG_IO = false;

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

    if(HE_DEBUG_IO) ESP_LOGI(TAG, "File read successfully: %d bytes", *out_size);
    return ESP_OK;
}

esp_err_t read_file_to_executable_memory(const char* file_path, uint8_t** out_data, size_t* out_size) {
    FILE* file = NULL;
    uint8_t* dma_buffer = NULL;
    
    if (file_path == NULL || out_data == NULL || out_size == NULL) {
        ESP_LOGE(TAG, "read_file_to_executable_memory: Invalid input parameters");
        return ESP_ERR_INVALID_ARG;
    }

    file = fopen(file_path, "rb");
    if (file == NULL) {
        ESP_LOGE(TAG, "read_file_to_executable_memory: Failed to open file: %s", file_path);
        return ESP_ERR_NOT_FOUND;
    }

    // Ottiene la dimensione del file
    fseek(file, 0, SEEK_END);
    *out_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    // Alloca memoria allineata e non cached
    dma_buffer = heap_caps_aligned_calloc(16, 1, *out_size, 
                                        MALLOC_CAP_INTERNAL |
                                        MALLOC_CAP_8BIT);
    if (dma_buffer == NULL) {
        ESP_LOGE(TAG, "read_file_to_executable_memory: Failed to allocate buffer");
        fclose(file);
        return ESP_ERR_NO_MEM;
    }

    // Legge il file nel buffer
    size_t bytes_read = fread(dma_buffer, 1, *out_size, file);
    fclose(file);

    if (bytes_read != *out_size) {
        ESP_LOGE(TAG, "read_file_to_executable_memory: Failed to read file");
        heap_caps_free(dma_buffer);
        return ESP_FAIL;
    }

    // Sincronizza la memoria
    //esp_rom_Cache_Flush(0);
    //esp_rom_Cache_Invalidate(0);

    *out_data = dma_buffer;
    if(HE_DEBUG_IO) ESP_LOGI(TAG, "read_file_to_executable_memory: File loaded into memory: %d bytes at %p", *out_size, dma_buffer);
    
    return ESP_OK;
}

void free_executable_memory(uint8_t* buffer) {
    if (buffer) {
        heap_caps_free(buffer);
    }
}

esp_err_t prepend_mount_point(const char* filename, char* full_path) {
    if (filename == NULL || full_path == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (strlen(SD_MOUNT_POINT) + strlen(filename) + 1 > MAX_FILENAME) {
        return ESP_ERR_INVALID_SIZE;
    }

    strcpy(full_path, SD_MOUNT_POINT);
    strcat(full_path, "/");
    strcat(full_path, filename);

    return ESP_OK;
}

esp_err_t prepend_cwd(const char* cwd, char* full_path) {
    if (cwd == NULL || full_path == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (strlen(cwd) + strlen(full_path) + 1 > MAX_FILENAME) {
        return ESP_ERR_INVALID_SIZE;
    }

    char* filename = malloc(MAX_FILENAME*sizeof(char));
    strcpy(filename, full_path);
    strcpy(full_path, cwd);
    strcat(full_path, filename);

    free(filename);

    return ESP_OK;
}

esp_err_t create_dir_if_not_exist(const char* path) {
    struct stat st;
    esp_err_t ret = ESP_OK;

    // Verifica se la directory esiste
    if (stat(path, &st) != 0) {
        // La directory non esiste, proviamo a crearla
        if (mkdir(path, 0755) != 0) {
            ESP_LOGE(TAG, "Failed to create directory: %s", path);
            ret = ESP_FAIL;
        } else {
            ESP_LOGI(TAG, "Directory created: %s", path);
        }
    } else {
        // La directory esiste già
        ESP_LOGI(TAG, "Directory already exists: %s", path);
    }

    return ret;
}

esp_err_t write_data_chunk(const char* filename, const uint8_t* data, size_t chunk_size, size_t offset) {
   FILE* f = fopen(filename, "r+");
   if (f == NULL) {
       f = fopen(filename, "w");
   }
   if (f == NULL) {
       return ESP_FAIL;
   }

   fseek(f, offset, SEEK_SET);
   size_t written = fwrite(data, 1, chunk_size, f);
   fclose(f);

   return (written == chunk_size) ? ESP_OK : ESP_FAIL;
}

esp_err_t read_data_chunk(const char* filename, uint8_t* buffer, size_t chunk_size, size_t offset) {
   FILE* f = fopen(filename, "r");
   if (f == NULL) {
       return ESP_FAIL;
   }

   fseek(f, offset, SEEK_SET);
   size_t read = fread(buffer, 1, chunk_size, f);
   fclose(f);

   return (read == chunk_size) ? ESP_OK : ESP_FAIL;
}

///
///
///

void list_files(const char* dirname) {
    DIR *dir = opendir(dirname);
    if (dir == NULL) {
        ESP_LOGE(TAG, "Failed to open directory: %s", dirname);
        return;
    }

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        // Per file che non sono directory
        if (entry->d_type != DT_DIR) {
            char fullpath[MAX_FILENAME*2];
            snprintf(fullpath, sizeof(fullpath), "%s%s", dirname, entry->d_name);
            
            struct stat st = {0};
            if (stat(fullpath, &st) == 0) {
                float kb = (float)st.st_size / 1024.0;  // Convert to kilobytes
                ESP_LOGI(TAG, "%s \t %.2f KB", entry->d_name, kb);
            }
            else {
                ESP_LOGI(TAG, "%s", entry->d_name);
            }
        }
    }
    closedir(dir);
}