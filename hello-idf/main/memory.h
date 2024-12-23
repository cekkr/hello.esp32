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

// Integration points per il sistema di memoria segmentata
typedef struct {
    // Funzione per notificare il sistema quando un segmento dev'essere paginato
    esp_err_t (*request_segment_paging)(uint32_t segment_id, size_t size);
    
    // Funzione per notificare quando un segmento deve essere ricaricato in memoria
    esp_err_t (*request_segment_load)(uint32_t segment_id);
    
    // Funzione per ottenere lo stato attuale della memoria
    size_t (*get_available_memory)(void);
    
    // Funzione per convertire segment_id e offset in puntatore
    void* (*get_segment_pointer)(uint32_t segment_id, size_t offset);
} segment_handlers_t;

typedef struct {
    uint32_t segment_id;
    size_t size;
    size_t offset;
    bool is_paged;
    bool is_modified;
    uint32_t access_count;
    uint64_t last_access;
    float usage_frequency;
} segment_info_t;

typedef struct {
    segment_info_t* segments;
    uint32_t num_segments;
    size_t total_memory;
    size_t available_memory;
    
    // Statistiche
    uint32_t page_faults;
    uint32_t page_writes;
    float avg_segment_lifetime;
    uint32_t hot_segments;

    segment_handlers_t* handlers;
} paging_stats_t;

//static paging_stats_t g_stats = {0};
//static segment_handlers_t g_stats->handlers = {0};

esp_err_t paging_init(paging_stats_t* g_stats, segment_handlers_t* handlers, uint32_t max_segments) {    
    if (!handlers || !handlers->request_segment_paging || 
        !handlers->request_segment_load || !handlers->get_available_memory ||
        !handlers->get_segment_pointer) {
        return ESP_ERR_INVALID_ARG;
    }

    g_stats = malloc(sizeof(paging_stats_t));
    
    g_stats->segments = calloc(max_segments, sizeof(segment_info_t));
    if (!g_stats->segments) {
        return ESP_ERR_NO_MEM;
    }
    
    //memcpy(&g_stats->handlers, handlers, sizeof(segment_handlers_t));
    g_stats->handlers = handlers;

    g_stats->total_memory = g_stats->handlers->get_available_memory();
    g_stats->available_memory = g_stats->total_memory;
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_allocation(paging_stats_t* g_stats, uint32_t segment_id, size_t size, size_t offset) {
    // Verifica se il segmento esiste già
    for (int i = 0; i < g_stats->num_segments; i++) {
        if (g_stats->segments[i].segment_id == segment_id) {
            return ESP_ERR_INVALID_STATE;
        }
    }
    
    // Se abbiamo raggiunto il limite, riallochiamo con 8 segmenti in più
    if (g_stats->num_segments % 8 == 0) {
        size_t new_size = (g_stats->num_segments + 8) * sizeof(segment_info_t);
        segment_info_t* new_segments = realloc(g_stats->segments, new_size);
        if (!new_segments) {
            return ESP_ERR_NO_MEM;
        }
        g_stats->segments = new_segments;
    }
    
    segment_info_t* segment = &g_stats->segments[g_stats->num_segments++];
    segment->segment_id = segment_id;
    segment->size = size;
    segment->offset = offset;
    segment->is_paged = false;
    segment->is_modified = false;
    segment->access_count = 0;
    segment->last_access = esp_timer_get_time();
    segment->usage_frequency = 0.0f;
    
    // Aggiorna memoria disponibile
    g_stats->available_memory = g_stats->handlers->get_available_memory();
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_access(paging_stats_t* g_stats, uint32_t segment_id) {
    segment_info_t* target = NULL;
    
    for (int i = 0; i < g_stats->num_segments; i++) {
        if (g_stats->segments[i].segment_id == segment_id) {
            target = &g_stats->segments[i];
            break;
        }
    }
    
    if (!target) {
        return ESP_ERR_NOT_FOUND;
    }
    
    if (target->is_paged) {
        esp_err_t err = g_stats->handlers->request_segment_load(segment_id);
        if (err != ESP_OK) {
            return err;
        }
        target->is_paged = false;
        g_stats->page_faults++;
    }
    
    // Aggiorna statistiche
    uint64_t current_time = esp_timer_get_time();
    float alpha = 0.3f;
    target->usage_frequency = (alpha * (float)target->access_count) + 
                            ((1.0f - alpha) * target->usage_frequency);
    target->access_count = 1;
    target->last_access = current_time;
    
    // Verifica necessità di paging per altri segmenti
    g_stats->available_memory = g_stats->handlers.get_available_memory();
    float total_frequency = 0.0f;
    g_stats->hot_segments = 0;
    
    for (int i = 0; i < g_stats->num_segments; i++) {
        segment_info_t* segment = &g_stats->segments[i];
        total_frequency += segment->usage_frequency;
        
        if (!segment->is_paged && segment->size > (32 * 1024) && 
            segment->usage_frequency < g_stats->avg_segment_lifetime &&
            g_stats->available_memory < (g_stats->total_memory / 4)) {
            
            esp_err_t err = g_stats->handlers->request_segment_paging(segment->segment_id, 
                                                            segment->size);
            if (err != ESP_OK) {
                return err;
            }
            
            segment->is_paged = true;
            g_stats->page_writes++;
        }
        
        if (segment->usage_frequency > g_stats->avg_segment_lifetime) {
            g_stats->hot_segments++;
        }
    }
    
    g_stats->avg_segment_lifetime = total_frequency / g_stats->num_segments;
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_modification(paging_stats_t* g_stats, uint32_t segment_id) {
    for (int i = 0; i < g_stats->num_segments; i++) {
        if (g_stats->segments[i].segment_id == segment_id) {
            g_stats->segments[i].is_modified = true;
            return ESP_OK;
        }
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t paging_notify_segment_deallocation(paging_stats_t* g_stats, uint32_t segment_id) {
    for (int i = 0; i < g_stats->num_segments; i++) {
        if (g_stats->segments[i].segment_id == segment_id) {
            memmove(&g_stats->segments[i], 
                   &g_stats->segments[i + 1],
                   (g_stats->num_segments - i - 1) * sizeof(segment_info_t));
            g_stats->num_segments--;
            g_stats->available_memory = g_stats->handlers->get_available_memory();
            return ESP_OK;
        }
    }
    return ESP_ERR_NOT_FOUND;
}

/*const paging_stats_t* paging_get_stats(void) {
    return &g_stats;
}*/

/* Example

#include <esp_err.h>
#include <esp_heap_caps.h>
#include "paging_system.h"

typedef struct {
    void* base_ptr;
    size_t size;
    uint32_t id;
    bool is_allocated;
} segment_t;

#define MAX_SEGMENTS 32
static segment_t segments[MAX_SEGMENTS];
static size_t total_allocated = 0;

static esp_err_t handle_segment_paging(uint32_t segment_id, size_t size) {
    segment_t* seg = &segments[segment_id];
    
    // Salva il segmento in filesystem
    const char* filename = generate_filename(segment_id);
    esp_err_t err = write_data_chunk(filename, seg->base_ptr, size, 0);
    if (err != ESP_OK) return err;
    
    // Libera la memoria
    heap_caps_free(seg->base_ptr);
    seg->base_ptr = NULL;
    total_allocated -= seg->size;
    
    return ESP_OK;
}

static esp_err_t handle_segment_load(uint32_t segment_id) {
    segment_t* seg = &segments[segment_id];
    
    // Riallocazione memoria
    seg->base_ptr = heap_caps_malloc(seg->size, MALLOC_CAP_DEFAULT);
    if (!seg->base_ptr) return ESP_ERR_NO_MEM;
    
    // Ricarica dati da filesystem
    const char* filename = generate_filename(segment_id);
    esp_err_t err = read_data_chunk(filename, seg->base_ptr, seg->size, 0);
    if (err != ESP_OK) {
        heap_caps_free(seg->base_ptr);
        seg->base_ptr = NULL;
        return err;
    }
    
    total_allocated += seg->size;
    return ESP_OK;
}

static size_t get_free_memory(void) {
    return heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
}

static void* get_segment_ptr(uint32_t segment_id, size_t offset) {
    if (segment_id >= MAX_SEGMENTS || !segments[segment_id].is_allocated) 
        return NULL;
    return segments[segment_id].base_ptr + offset;
}

void init_memory_system(void) {
    segment_handlers_t handlers = {
        .request_segment_paging = handle_segment_paging,
        .request_segment_load = handle_segment_load,
        .get_available_memory = get_free_memory,
        .get_segment_pointer = get_segment_ptr
    };
    
    paging_init(&handlers, MAX_SEGMENTS);
}

void* allocate_memory(size_t size, uint32_t* segment_id) {
    // Trova slot libero
    uint32_t id;
    for (id = 0; id < MAX_SEGMENTS; id++) {
        if (!segments[id].is_allocated) break;
    }
    if (id == MAX_SEGMENTS) return NULL;
    
    void* ptr = heap_caps_malloc(size, MALLOC_CAP_DEFAULT);
    if (!ptr) return NULL;
    
    segments[id].base_ptr = ptr;
    segments[id].size = size;
    segments[id].id = id;
    segments[id].is_allocated = true;
    total_allocated += size;
    
    // Notifica paging system
    paging_notify_segment_allocation(id, size, 0);
    
    *segment_id = id;
    return ptr;
}

void* access_memory(uint32_t segment_id, size_t offset) {
    if (segment_id >= MAX_SEGMENTS || !segments[segment_id].is_allocated)
        return NULL;
        
    // Notifica accesso al paging system
    paging_notify_segment_access(segment_id);
    
    return segments[segment_id].base_ptr + offset;
}

void free_memory(uint32_t segment_id) {
    if (segment_id >= MAX_SEGMENTS || !segments[segment_id].is_allocated)
        return;
        
    heap_caps_free(segments[segment_id].base_ptr);
    total_allocated -= segments[segment_id].size;
    
    // Notifica deallocazione
    paging_notify_segment_deallocation(segment_id);
    
    memset(&segments[segment_id], 0, sizeof(segment_t));
}

// Esempio di utilizzo
void example(void) {
    uint32_t seg_id;
    void* ptr = allocate_memory(1024, &seg_id); // Alloca 1KB
    
    uint8_t* data = access_memory(seg_id, 0);
    data[0] = 42; // Scrittura
    paging_notify_segment_modification(seg_id);
    
    // Il paging system deciderà automaticamente quando fare paging
    
    free_memory(seg_id);
}

*/