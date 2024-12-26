#ifndef HELLOESP_IO
#define HELLOESP_IO
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <sys/stat.h>
#include "esp_err.h"


esp_err_t read_file_to_memory(const char* file_path, uint8_t** out_data, size_t* out_size);
esp_err_t read_file_to_executable_memory(const char* file_path, uint8_t** out_data, size_t* out_size);
void free_executable_memory(uint8_t* buffer);
esp_err_t prepend_mount_point(const char* filename, char* full_path);
esp_err_t prepend_cwd(const char* cwd, char* full_path);

bool file_exists(const char* path);
esp_err_t create_dir_if_not_exist(const char* path);
esp_err_t write_data_chunk(const char* filename, const uint8_t* data, size_t chunk_size, size_t offset);
esp_err_t read_data_chunk(const char* filename, uint8_t* buffer, size_t chunk_size, size_t offset);

void list_files(const char* dirname);

#endif  // HELLOESP_IO