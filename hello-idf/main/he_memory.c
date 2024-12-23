#include "he_memory.h"

#include <esp_err.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <string.h>
#include <stdio.h>
#include <inttypes.h>
#include "esp_timer.h"

#include "he_defines.h"
#include "he_sdcard.h"

#include "he_io.h"

///
///
///

char* create_segment_page_name(char* basePath, int segment_id){
    char* name = malloc(sizeof(char)*MAX_FILENAME);
    sprintf(name, "%s-%d.bin", basePath, segment_id);
    return name;
}

///
///
///

size_t default_get_available_memory(paging_stats_t* g_stats){
    return heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
}

esp_err_t default_request_segment_paging(paging_stats_t* g_stats, uint32_t segment_id){
    segment_info_t* segment = &g_stats->segments[segment_id];
    char* pageName = create_segment_page_name(g_stats->base_path, segment_id);
    esp_err_t res = write_data_chunk(pageName, segment->data, g_stats->segment_size, 0);
    free(pageName);
    return res;
}

esp_err_t default_request_segment_load(paging_stats_t* g_stats, uint32_t segment_id){
    segment_info_t* segment = &g_stats->segments[segment_id];
    char* pageName = create_segment_page_name(g_stats->base_path, segment_id);
    esp_err_t res = read_data_chunk(pageName, segment->data, g_stats->segment_size, 0);
    free(pageName);
    return res;
}

///
///
///

#include "esp_random.h"
char* generate_random_session_number() {
    static char str[5];
    uint32_t num = esp_random() % 10000;
    sprintf(str, "%04d", num);
    return str;
}

///
///
///

//static paging_stats_t g_stats = {0};
//static segment_handlers_t g_stats->handlers = {0};

esp_err_t paging_init(paging_stats_t* g_stats, segment_handlers_t* handlers, size_t segment_size) {    

    if(!handlers) {
        return ESP_ERR_INVALID_ARG;
    }

    if(handlers->get_available_memory == NULL){
        handlers->get_available_memory = &default_get_available_memory;
    }

    if(handlers->request_segment_paging == NULL){
        handlers->request_segment_paging = &default_request_segment_paging;
    }

    if(handlers->request_segment_load == NULL){
        handlers->request_segment_load = &default_request_segment_load;
    }

    g_stats = malloc(sizeof(paging_stats_t));
    
    if(!g_stats) {
        return ESP_ERR_NO_MEM;
    }

    // Create paging path
    g_stats->name = generate_random_session_number();
    create_dir_if_not_exist(PAGING_PATH);

    char* pagingPath = malloc(sizeof(char)*MAX_FILENAME);
    if (!pagingPath) {
        return ESP_ERR_NO_MEM;
    }
    strcpy(pagingPath, PAGING_PATH);
    strcat(pagingPath, "/");
    strcat(pagingPath, g_stats->name);

    g_stats->base_path = pagingPath;

    // Manage segments
    g_stats->segment_size = segment_size;
    g_stats->segments = calloc(ALLOC_SEGMENTS_INFO_BY, sizeof(segment_info_t));
    if (!g_stats->segments) {
        return ESP_ERR_NO_MEM;
    }
    
    //memcpy(&g_stats->handlers, handlers, sizeof(segment_handlers_t));
    g_stats->handlers = handlers;

    g_stats->total_memory = g_stats->handlers->get_available_memory(g_stats);
    g_stats->available_memory = g_stats->total_memory;

    g_stats->set_access_as_modified = true;
    
    return ESP_OK;
}

esp_err_t paging_deinit(paging_stats_t * g_stats){
    if(g_stats){
        for(uint32_t s=0; s<g_stats->num_segments; s++){
            //todo: something
        }

        free(g_stats->segments);
        free(g_stats->base_path);
        free(g_stats);
    }
}

esp_err_t paging_notify_segment_allocation(paging_stats_t* g_stats, uint32_t segment_id, size_t offset) {
    // Verifica se il segmento esiste già
    if (g_stats->num_segments < segment_id && g_stats->segments[segment_id].segment_id == segment_id) {
        return ESP_ERR_INVALID_STATE;
    }
    
    // Se abbiamo raggiunto il limite, riallochiamo con 8 segmenti in più
    if (g_stats->num_segments % ALLOC_SEGMENTS_INFO_BY == 0) {
        size_t new_size = (g_stats->num_segments + ALLOC_SEGMENTS_INFO_BY) * sizeof(segment_info_t);
        segment_info_t* new_segments = realloc(g_stats->segments, new_size);
        if (!new_segments) {
            return ESP_ERR_NO_MEM;
        }
        g_stats->segments = new_segments;
    }
    
    segment_info_t* segment = &g_stats->segments[g_stats->num_segments++];
    segment->segment_id = segment_id;
    segment->size = g_stats->segment_size;
    segment->offset = offset;
    segment->is_paged = false;
    segment->is_modified = false;
    segment->access_count = 0;
    segment->last_access = esp_timer_get_time();
    segment->usage_frequency = 0.0f;
    
    // Aggiorna memoria disponibile
    g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_access(paging_stats_t* g_stats, uint32_t segment_id) {
    segment_info_t* target = NULL;
    
    if (g_stats->num_segments >= segment_id && g_stats->segments[segment_id].segment_id == segment_id) {
        target = &g_stats->segments[segment_id];
    }
    
    if (!target) {
        return ESP_ERR_NOT_FOUND;
    }

    g_stats->last_segment_id = segment_id;
    
    if (target->is_paged) {
        esp_err_t err = g_stats->handlers->request_segment_load(g_stats, segment_id);
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

    if(g_stats->set_access_as_modified){
        target->is_modified = true;
    }
    
    // Verifica necessità di paging per altri segmenti
    esp_err_t check_paging_needed = paging_check_paging_needed(g_stats);

    return check_paging_needed;
}

esp_err_t paging_check_paging_needed(paging_stats_t* g_stats){
    g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
    float total_frequency = 0.0f;
    g_stats->hot_segments = 0;
    
    for (int i = 0; i < g_stats->num_segments; i++) {
        if(g_stats->last_segment_id == i)
            continue;

        segment_info_t* segment = &g_stats->segments[i];
        total_frequency += segment->usage_frequency;
        
        if (!segment->is_paged && segment->usage_frequency < g_stats->avg_segment_lifetime &&
            g_stats->available_memory < (g_stats->total_memory / 4)) {
            
            esp_err_t err = g_stats->handlers->request_segment_paging(g_stats, segment->segment_id);
            if (err != ESP_OK) {
                return err;
            }
            
            segment->is_paged = true;
            segment->has_page = true;   

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
    if (g_stats->num_segments >= segment_id && g_stats->segments[segment_id].segment_id == segment_id) {
        g_stats->segments[segment_id].is_modified = true;
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t paging_notify_segment_deallocation(paging_stats_t* g_stats, uint32_t segment_id) {
    if (g_stats->num_segments < segment_id && g_stats->segments[segment_id].segment_id == segment_id) {
        uint32_t i = segment_id;
        if (g_stats->segments[i].segment_id == segment_id) {
            segment_info_t* seg = &g_stats->segments[i];
            seg->has_page = false;
            seg->data = NULL;
            seg->is_modified = false;
            seg->is_paged = false;
            seg->access_count = 0;
            seg->usage_frequency = 0.0f;

            g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
            return ESP_OK;
        }
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t paging_notify_segment_remove(paging_stats_t* g_stats, uint32_t segment_id) {
    if (g_stats->num_segments < segment_id && g_stats->segments[segment_id].segment_id == segment_id) {
        uint32_t i = segment_id;
        if (g_stats->segments[i].segment_id == segment_id) {
            memmove(&g_stats->segments[i], 
                   &g_stats->segments[i + 1],
                   (g_stats->num_segments - i - 1) * sizeof(segment_info_t));
            g_stats->num_segments--;
            g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
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
