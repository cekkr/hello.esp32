#pragma once

#include <esp_err.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <string.h>
#include <stdio.h>
#include "esp_timer.h"

#include "defines.h"
#include "sdcard.h"

void init_paging_point(){
    create_dir_if_not_exist(PAGING_PATH);
}

///
/// Data chunk
///

// Scrive un chunk di dati in un file
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

// Legge un chunk di dati da un file 
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

#define PAGING_THRESHOLD_BYTES (32 * 1024)  // 32KB
#define MAX_FILENAME_LEN 64
#define STATS_HISTORY_SIZE 10

typedef struct {
    void* base_addr;
    size_t size;
    uint32_t segment_id;
    uint32_t access_count;
    uint64_t last_access;
    float usage_frequency;    // accessi/tempo
    bool is_paged;
    bool is_modified;
} segment_stats_t;

typedef struct {
    segment_stats_t* segments;
    uint32_t num_segments;
    size_t total_memory;
    size_t available_memory;
    uint64_t access_counter;
    
    // Statistiche globali
    struct {
        uint32_t page_faults;
        uint32_t page_writes;
        float avg_segment_lifetime;
        uint32_t hot_segments;  // segmenti con usage_frequency > media
    } global_stats;
} memory_manager_t;

static memory_manager_t g_mem_manager = {0};

// Funzioni di integrazione con il sistema di memoria segmentata esistente
__attribute__((weak)) extern void* get_segment_base(uint32_t segment_id);
__attribute__((weak)) extern size_t get_segment_size(uint32_t segment_id);
__attribute__((weak)) extern bool is_segment_allocated(uint32_t segment_id);
__attribute__((weak)) extern esp_err_t allocate_segment(uint32_t segment_id, size_t size);
__attribute__((weak)) extern esp_err_t free_segment(uint32_t segment_id);

static char* generate_page_filename(uint32_t segment_id, uint32_t chunk_id) {
    static char filename[MAX_FILENAME_LEN];
    snprintf(filename, MAX_FILENAME_LEN, "/spiffs/seg%u_chunk%u.page", segment_id, chunk_id);
    return filename;
}

static void update_segment_statistics(segment_stats_t* segment) {
    uint64_t current_time = esp_timer_get_time();
    uint64_t time_diff = current_time - segment->last_access;
    
    // Aggiorna frequenza di utilizzo con media mobile esponenziale
    float alpha = 0.3f;  // fattore di smoothing
    segment->usage_frequency = (alpha * (float)segment->access_count) + 
                             ((1.0f - alpha) * segment->usage_frequency);
    
    segment->access_count = 1;
    segment->last_access = current_time;
}

static bool should_page_out_segment(segment_stats_t* segment) {
    // Decisione basata su:
    // 1. Memoria disponibile
    // 2. Frequenza di utilizzo
    // 3. Dimensione del segmento
    
    if (g_mem_manager.available_memory < PAGING_THRESHOLD_BYTES &&
        segment->size > PAGING_THRESHOLD_BYTES &&
        segment->usage_frequency < g_mem_manager.global_stats.avg_segment_lifetime) {
        return true;
    }
    return false;
}

esp_err_t init_memory_manager(void) {
    g_mem_manager.segments = calloc(32, sizeof(segment_stats_t));  // Supporta fino a 32 segmenti
    if (!g_mem_manager.segments) {
        return ESP_ERR_NO_MEM;
    }
    
    g_mem_manager.num_segments = 0;
    g_mem_manager.total_memory = heap_caps_get_total_size(MALLOC_CAP_DEFAULT);
    g_mem_manager.available_memory = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
    
    return ESP_OK;
}

esp_err_t register_segment(uint32_t segment_id, size_t size) {
    if (g_mem_manager.num_segments >= 32) {
        return ESP_ERR_NO_MEM;
    }
    
    segment_stats_t* segment = &g_mem_manager.segments[g_mem_manager.num_segments++];
    segment->segment_id = segment_id;
    segment->size = size;
    segment->base_addr = get_segment_base(segment_id);
    segment->access_count = 0;
    segment->last_access = esp_timer_get_time();
    segment->usage_frequency = 0.0f;
    segment->is_paged = false;
    segment->is_modified = false;
    
    return ESP_OK;
}

esp_err_t on_segment_access(uint32_t segment_id) {
    segment_stats_t* segment = NULL;
    
    // Trova il segmento
    for (int i = 0; i < g_mem_manager.num_segments; i++) {
        if (g_mem_manager.segments[i].segment_id == segment_id) {
            segment = &g_mem_manager.segments[i];
            break;
        }
    }
    
    if (!segment) {
        return ESP_ERR_NOT_FOUND;
    }
    
    // Se il segmento è stato paginato, ricaricalo
    if (segment->is_paged) {
        // Alloca memoria per il segmento
        esp_err_t err = allocate_segment(segment_id, segment->size);
        if (err != ESP_OK) {
            return err;
        }
        
        segment->base_addr = get_segment_base(segment_id);
        
        // Carica i dati dal file system
        size_t remaining = segment->size;
        size_t offset = 0;
        uint32_t chunk_id = 0;
        
        while (remaining > 0) {
            size_t chunk_size = (remaining > PAGING_THRESHOLD_BYTES) ? 
                               PAGING_THRESHOLD_BYTES : remaining;
            
            const char* filename = generate_page_filename(segment_id, chunk_id);
            err = read_data_chunk(filename, 
                                segment->base_addr + offset,
                                chunk_size, 
                                0);
            if (err != ESP_OK) {
                return err;
            }
            
            remaining -= chunk_size;
            offset += chunk_size;
            chunk_id++;
        }
        
        segment->is_paged = false;
        g_mem_manager.global_stats.page_faults++;
    }
    
    // Aggiorna statistiche
    update_segment_statistics(segment);
    
    // Verifica se altri segmenti devono essere paginati
    for (int i = 0; i < g_mem_manager.num_segments; i++) {
        segment_stats_t* other = &g_mem_manager.segments[i];
        if (!other->is_paged && should_page_out_segment(other)) {
            // Salva il segmento su file system
            size_t remaining = other->size;
            size_t offset = 0;
            uint32_t chunk_id = 0;
            
            while (remaining > 0) {
                size_t chunk_size = (remaining > PAGING_THRESHOLD_BYTES) ? 
                                   PAGING_THRESHOLD_BYTES : remaining;
                
                const char* filename = generate_page_filename(other->segment_id, chunk_id);
                esp_err_t err = write_data_chunk(filename,
                                               other->base_addr + offset,
                                               chunk_size,
                                               0);
                if (err != ESP_OK) {
                    return err;
                }
                
                remaining -= chunk_size;
                offset += chunk_size;
                chunk_id++;
            }
            
            // Libera il segmento dalla RAM
            free_segment(other->segment_id);
            other->is_paged = true;
            other->base_addr = NULL;
            g_mem_manager.global_stats.page_writes++;
        }
    }
    
    // Aggiorna statistiche globali
    g_mem_manager.available_memory = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
    
    float total_frequency = 0.0f;
    g_mem_manager.global_stats.hot_segments = 0;
    
    for (int i = 0; i < g_mem_manager.num_segments; i++) {
        total_frequency += g_mem_manager.segments[i].usage_frequency;
        if (g_mem_manager.segments[i].usage_frequency > 
            g_mem_manager.global_stats.avg_segment_lifetime) {
            g_mem_manager.global_stats.hot_segments++;
        }
    }
    
    g_mem_manager.global_stats.avg_segment_lifetime = 
        total_frequency / g_mem_manager.num_segments;
    
    return ESP_OK;
}

esp_err_t on_segment_modify(uint32_t segment_id) {
    for (int i = 0; i < g_mem_manager.num_segments; i++) {
        if (g_mem_manager.segments[i].segment_id == segment_id) {
            g_mem_manager.segments[i].is_modified = true;
            return ESP_OK;
        }
    }
    return ESP_ERR_NOT_FOUND;
}

const memory_manager_t* get_memory_stats(void) {
    return &g_mem_manager;
}