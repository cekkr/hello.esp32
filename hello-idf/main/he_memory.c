#include "he_memory.h"

#include <esp_err.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <string.h>
#include <stdio.h>
#include "esp_timer.h"

#include "he_defines.h"
#include "he_io.h"
#include "he_device.h"

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
    g_stats->available_memory = heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    return g_stats->available_memory;
}

const bool HE_DEBUG_default_request_segment_paging = true;
esp_err_t default_request_segment_paging(paging_stats_t* g_stats, uint32_t segment_id){
    if(HE_DEBUG_default_request_segment_paging){
        ESP_LOGI(TAG, "default_request_segment_paging: requested paging for segment %u", segment_id);
    }

    segment_info_t* segment = g_stats->segments[segment_id];
    char* pageName = create_segment_page_name(g_stats->base_path, segment_id);
    if(HE_DEBUG_default_request_segment_paging) ESP_LOGI(TAG, "default_request_segment_paging: segment page name: %s", pageName);

    esp_err_t res = write_data_chunk(pageName, *segment->data, g_stats->segment_size, 0);
    free(pageName);

    if(res == ESP_OK){
        free(*segment->data);
        *segment->data = NULL;
    }

    return res;
}

const bool HE_DEBUG_default_request_segment_load = true;
esp_err_t default_request_segment_load(paging_stats_t* g_stats, uint32_t segment_id){
    if(HE_DEBUG_default_request_segment_load){
        ESP_LOGI(TAG, "default_request_segment_load: requested page load for segment %u", segment_id);
    }

    segment_info_t* segment = g_stats->segments[segment_id];
    char* pageName = create_segment_page_name(g_stats->base_path, segment_id);
    if(HE_DEBUG_default_request_segment_load){ 
        ESP_LOGI(TAG, "default_request_segment_load: segment page name: %s", pageName);
        ESP_LOGI(TAG, "default_request_segment_load: read_data_chunk buffer: %p, chunk_size: %ld", *segment->data, g_stats->segment_size);
    }

    if(!file_exists){
        if(HE_DEBUG_default_request_segment_load){
            ESP_LOGE(TAG, "default_request_segment_load: page %s does not exist", pageName);
        }
        return ESP_ERR_NOT_FOUND;
    }

    esp_err_t res = read_data_chunk(pageName, *segment->data, g_stats->segment_size, 0);
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

const bool HE_DEBUG_paging_init = false;
esp_err_t paging_init(paging_stats_t** _g_stats, segment_handlers_t* handlers, size_t segment_size) {    

    if(!handlers) {
        return ESP_ERR_INVALID_ARG;
    }

    if(handlers->get_available_memory == NULL){
        if(HE_DEBUG_paging_init) ESP_LOGI(TAG, "paging_init: setting default get_available_memory (%p)", default_get_available_memory);
        handlers->get_available_memory = &default_get_available_memory;
    }

    if(handlers->request_segment_paging == NULL){
        if(HE_DEBUG_paging_init) ESP_LOGI(TAG, "paging_init: setting default request_segment_paging (%p)", default_request_segment_paging);
        handlers->request_segment_paging = &default_request_segment_paging;
    }

    if(handlers->request_segment_load == NULL){
        if(HE_DEBUG_paging_init) ESP_LOGI(TAG, "paging_init: setting default request_segment_load (%p)", default_request_segment_load);
        handlers->request_segment_load = &default_request_segment_load;
    }

    if(HE_DEBUG_paging_init){
        ESP_LOGI(TAG, "paging_init: handlers: %p, segment_size: %zu", handlers, segment_size);
        ESP_LOGI(TAG, "paging_init: handlers->get_available_memory: %p", handlers->get_available_memory);
        ESP_LOGI(TAG, "paging_init: handlers->request_segment_paging: %p", handlers->request_segment_paging);
        ESP_LOGI(TAG, "paging_init: handlers->request_segment_load: %p", handlers->request_segment_load);
    }

    *_g_stats = malloc(sizeof(paging_stats_t));
    memset(*_g_stats, 0, sizeof(paging_stats_t));
    
    paging_stats_t* g_stats = *_g_stats;
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
    g_stats->num_segments = 0;
    g_stats->segments = calloc(ALLOC_SEGMENTS_INFO_BY, sizeof(segment_info_t*));
    if (!g_stats->segments) {
        return ESP_ERR_NO_MEM;
    }
    
    // not working: g_stats->handlers = handlers;    
    g_stats->handlers = malloc(sizeof(segment_handlers_t));
    if (!g_stats->handlers) {
        return ESP_ERR_NO_MEM;
    }
    memcpy(g_stats->handlers, handlers, sizeof(segment_handlers_t));
    
    g_stats->total_memory = heap_caps_get_total_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);;
    g_stats->handlers->get_available_memory(g_stats);

    g_stats->set_access_as_modified = true;
    
    return ESP_OK;
}

esp_err_t paging_delete_segment_page(paging_stats_t * g_stats, segment_info_t * segment){
    char* pageName = create_segment_page_name(g_stats->base_path, segment->segment_id);
    esp_err_t res = unlink(pageName);

    if(res == ESP_OK){
        segment->has_page = false;
        segment->is_paged = false;
    }

    free(pageName);
    return res;
}

esp_err_t paging_deinit(paging_stats_t * g_stats){
    if(g_stats){
        for(uint32_t s=0; s<g_stats->num_segments; s++){
            if(g_stats->segments[s]->has_page){
                paging_delete_segment_page(g_stats, &g_stats->segments[s]);
            }
        }

        free(g_stats->segments);
        free(g_stats->base_path);
        free(g_stats);
    }
}

const bool HE_DEBUG_paging_notify_segment_creation = false;
esp_err_t paging_notify_segment_creation(paging_stats_t* g_stats, segment_info_t** segment) {
    size_t offset = 0; // default value
    uint32_t segment_id = g_stats->num_segments++;

    // For the moment, this check is always true
    if (false && g_stats->num_segments < segment_id && g_stats->segments[segment_id]->segment_id == segment_id) {
        return ESP_ERR_INVALID_STATE;
    }
    
    // Se abbiamo raggiunto il limite, riallochiamo con 8 segmenti in più
    if (g_stats->num_segments % ALLOC_SEGMENTS_INFO_BY == 0) {
        size_t new_size = (g_stats->num_segments + ALLOC_SEGMENTS_INFO_BY) * sizeof(segment_info_t*);

        if(HE_DEBUG_paging_notify_segment_creation){
            ESP_LOGI(TAG, "paging_notify_segment_creation: reallocating g_stats->segments to %zu bytes", new_size);
        }

        segment_info_t** new_segments = realloc(g_stats->segments, new_size);
        if (new_segments == NULL) {
            ESP_LOGW(TAG, "paging_notify_segment_creation: realloc of g_stats->segments failed (%p, %p)", g_stats->segments, new_segments);
            return ESP_ERR_NO_MEM;
        }
        g_stats->segments = new_segments;
    }        

    segment_info_t* seg = malloc(sizeof(segment_info_t));   
    memset(seg, 0, sizeof(segment_info_t)); 

    if(HE_DEBUG_paging_notify_segment_creation && false){
        ESP_LOGI(TAG, "paging_notify_segment_creation: segment_id: %u, offset: %zu", segment_id, offset);
        ESP_LOGI(TAG, "paging_notify_segment_creation: g_stats->num_segments: %u", g_stats->num_segments);
        ESP_LOGI(TAG, "paging_notify_segment_creation: seg: %p", seg);
        ESP_LOGI(TAG, "paging_notify_segment_creation: g_stats->segments[segment_id]: %p", g_stats->segments[segment_id]);
    }

    if(seg == NULL){        
        ESP_LOGE(TAG, "paging_notify_segment_creation: segment malloc failed");
        print_ram_info();
        return ESP_ERR_NO_MEM;
    }

    g_stats->segments[segment_id] = seg;
    *segment = seg;

    seg->segment_id = segment_id;
    seg->data = NULL;
    seg->size = g_stats->segment_size;
    seg->offset = offset;
    seg->is_paged = false;
    seg->has_page = false;
    seg->is_modified = false;
    seg->is_allocated = false;
    seg->access_count = 0;
    seg->last_access = esp_timer_get_time();
    seg->usage_frequency = 0.0f;
    
    // Aggiorna memoria disponibile
    g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_allocation(paging_stats_t* g_stats, segment_info_t* segment, void** data) {
    if(data == NULL){
        ESP_LOGE(TAG, "paging_notify_segment_allocation: data is NULL");
        return ESP_ERR_INVALID_ARG;
    }

    segment->data = data;
    segment->is_allocated = true;

    //todo: ...

    return ESP_OK;
}

const bool HE_DEBUG_paging_notify_segment_access = true;
esp_err_t paging_notify_segment_access(paging_stats_t* g_stats, uint32_t segment_id) {
    segment_info_t* target = NULL;
    
    if (g_stats->num_segments >= segment_id && g_stats->segments[segment_id]->segment_id == segment_id) {
        target = g_stats->segments[segment_id];
    }
    
    if (!target) {
        return ESP_ERR_NOT_FOUND;
    }

    if(HE_DEBUG_paging_notify_segment_access)
        ESP_LOGI("WASM3", "paging_notify_segment_access: target: %p", target);

    g_stats->last_segment_id = segment_id;
    
    if (target->is_paged && target->is_allocated) {
        if(HE_DEBUG_paging_notify_segment_access) ESP_LOGI("WASM3", "paging_notify_segment_access: request segment load for segment %d", segment_id);
        esp_err_t err = g_stats->handlers->request_segment_load(g_stats, segment_id);
        if (err != ESP_OK) {
            g_stats->page_faults++;
            ESP_LOGE(TAG, "paging_notify_segment_access: failed loading segment %d", segment_id);
            return err;
        }
        target->is_paged = false;        
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
    if(HE_DEBUG_paging_notify_segment_access){
        ESP_LOGI("WASM3", "paging_notify_segment_access: g_stats: %p", g_stats); 
        ESP_LOGI("WASM3", "Calling paging_check_paging_needed at %p", paging_check_paging_needed);
    }

    esp_err_t check_paging_needed = paging_check_paging_needed(g_stats);

    return check_paging_needed;
}

const bool HE_DEBUG_paging_check_paging_needed = false;
esp_err_t paging_check_paging_needed(paging_stats_t* g_stats){
    if(HE_DEBUG_paging_check_paging_needed){
        ESP_LOGI(TAG, "paging_check_paging_needed: g_stats: %p", g_stats); 
        ESP_LOGI(TAG, "paging_check_paging_needed: g_stats->handlers->get_available_memory: %p", g_stats->handlers->get_available_memory); 
    }    

    if(HE_DEBUG_paging_check_paging_needed){
        ESP_LOGI(TAG, "paging_check_paging_needed: g_stats->handlers->get_available_memory executed (%lu)", g_stats->available_memory);
    }

    float total_frequency = 0.0f;
    g_stats->hot_segments = 0;
    
    for (int i = 0; i < g_stats->num_segments; i++) {
        if(g_stats->last_segment_id == i)
            continue;

        segment_info_t* segment = g_stats->segments[i];
        total_frequency += segment->usage_frequency;

        g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
        if(g_stats->available_memory > (g_stats->total_memory / 3)){
            break;
        }
        
        if (*segment->data != NULL && !segment->is_paged && segment->usage_frequency < g_stats->avg_segment_lifetime) {
            
            if(HE_DEBUG_paging_check_paging_needed){
                ESP_LOGI(TAG, "paging_check_paging_needed: calling g_stats->handlers->request_segment_paging (%p)", g_stats->handlers->request_segment_paging);
            }

            esp_err_t err = g_stats->handlers->request_segment_paging(g_stats, segment->segment_id);
            if (err == ESP_OK) {
                segment->is_paged = true;
                segment->has_page = true;   

                g_stats->page_writes++;
                g_stats->available_memory -= g_stats->segment_size;
            }
            else {
                g_stats->page_faults++;
                ESP_LOGW(TAG, "paging_check_paging: failed segment %d paging with error: %d", segment->segment_id, err);
            }
        }
        
        if (segment->usage_frequency > g_stats->avg_segment_lifetime) {
            g_stats->hot_segments++;
        }
    }
    
    g_stats->avg_segment_lifetime = total_frequency / g_stats->num_segments;
    
    return ESP_OK;
}

esp_err_t paging_notify_segment_modification(paging_stats_t* g_stats, uint32_t segment_id) {
    if (g_stats->num_segments >= segment_id && g_stats->segments[segment_id]->segment_id == segment_id) {
        g_stats->segments[segment_id]->is_modified = true;
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t paging_notify_segment_deallocation(paging_stats_t* g_stats, uint32_t segment_id) {
    if (g_stats->num_segments < segment_id && g_stats->segments[segment_id]->segment_id == segment_id) {
        uint32_t i = segment_id;
        if (g_stats->segments[i]->segment_id == segment_id) {
            segment_info_t* seg = &g_stats->segments[i];

            esp_err_t res = ESP_OK;
            if(seg->has_page){
                res = paging_delete_segment_page(g_stats, seg);
            }

            seg->has_page = false;
            seg->is_allocated = false;
            seg->is_modified = false;
            seg->is_paged = false;
            seg->access_count = 0;
            seg->usage_frequency = 0.0f;

            g_stats->available_memory = g_stats->handlers->get_available_memory(g_stats);
            return res;
        }
    }
    return ESP_ERR_NOT_FOUND;
}

// DON'T use it in M3Memory
esp_err_t paging_notify_segment_remove(paging_stats_t* g_stats, uint32_t segment_id) {
    if (g_stats->num_segments < segment_id && g_stats->segments[segment_id]->segment_id == segment_id) {
        uint32_t i = segment_id;
        if (g_stats->segments[i]->segment_id == segment_id) {
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
