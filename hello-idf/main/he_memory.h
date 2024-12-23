#ifndef HELLOESP_MEMORY_H
#define HELLOESP_MEMORY_H

#include <esp_err.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <esp_err.h>
#include <esp_heap_caps.h>

#define ALLOC_SEGMENTS_INFO_BY 8

typedef struct paging_stats paging_stats_t;

// Integration points per il sistema di memoria segmentata
typedef struct segment_handlers {
    // Funzione per notificare il sistema quando un segmento dev'essere paginato
    esp_err_t (*request_segment_paging)(paging_stats_t* p_stats, uint32_t segment_id);
    
    // Funzione per notificare quando un segmento deve essere ricaricato in memoria
    esp_err_t (*request_segment_load)(paging_stats_t* p_stats, uint32_t segment_id);
    
    // Funzione per ottenere lo stato attuale della memoria
    size_t (*get_available_memory)(paging_stats_t* p_stats);
    
} segment_handlers_t;

typedef struct segment_info {
    uint32_t segment_id;
    size_t size;
    void* data;
    size_t offset;
    bool is_paged;
    bool has_page;
    bool is_modified;
    uint32_t access_count;
    uint64_t last_access;
    float usage_frequency;
} segment_info_t;

typedef struct paging_stats {
    char* name;
    char* base_path;

    segment_info_t* segments;
    uint32_t num_segments;
    size_t segment_size;
    size_t total_memory;
    size_t available_memory;

    bool set_access_as_modified;

    // Statistiche
    uint32_t page_faults;
    uint32_t page_writes;
    float avg_segment_lifetime;
    uint32_t hot_segments;

    segment_handlers_t* handlers;
} paging_stats_t;

esp_err_t paging_init(paging_stats_t* g_stats, segment_handlers_t* handlers, size_t segment_size);
esp_err_t paging_deinit(paging_stats_t * g_stats);
esp_err_t paging_notify_segment_allocation(paging_stats_t* g_stats, uint32_t segment_id, size_t offset);
esp_err_t paging_notify_segment_access(paging_stats_t* g_stats, uint32_t segment_id);
esp_err_t paging_notify_segment_modification(paging_stats_t* g_stats, uint32_t segment_id);
esp_err_t paging_notify_segment_deallocation(paging_stats_t* g_stats, uint32_t segment_id);
esp_err_t paging_notify_segment_remove(paging_stats_t* g_stats, uint32_t segment_id);

#endif