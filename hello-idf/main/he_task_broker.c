// task_broker.c
#include "he_task_broker.h"

static const char* TAG = "TASK_BROKER";

// Struttura per gestire le informazioni di ogni task
typedef struct {
    char name[MAX_TASK_NAME_LENGTH];
    QueueHandle_t queue;
    bool in_use;
} task_info_t;

// Variabili globali del broker
static struct {
    task_info_t tasks[MAX_TASKS];
    QueueHandle_t broker_queue;
    bool initialized;
} broker_ctx = {0};

// Funzione del task broker
static void broker_task(void *pvParameters) {
    broker_message_t message;
    
    while (1) {
        if (xQueueReceive(broker_ctx.broker_queue, &message, portMAX_DELAY)) {
            // Cerca il task destinatario
            for (int i = 0; i < MAX_TASKS; i++) {
                if (broker_ctx.tasks[i].in_use && 
                    strcmp(broker_ctx.tasks[i].name, message.destination) == 0) {
                    // Inoltra il messaggio alla coda del task destinatario
                    if (xQueueSend(broker_ctx.tasks[i].queue, &message, 0) != pdPASS) {
                        ESP_LOGW(TAG, "Failed to forward message to %s", message.destination);
                    }
                    break;
                }
            }
        }
    }
}

bool broker_init(void) {
    if (broker_ctx.initialized) {
        return true;
    }

    // Inizializza il contesto
    memset(&broker_ctx, 0, sizeof(broker_ctx));
    
    // Crea la coda principale del broker
    broker_ctx.broker_queue = xQueueCreate(BROKER_QUEUE_SIZE, sizeof(broker_message_t));
    if (!broker_ctx.broker_queue) {
        ESP_LOGE(TAG, "Failed to create broker queue");
        return false;
    }

    // Crea il task del broker
    BaseType_t ret = xTaskCreate(broker_task, "broker_task", 4096, NULL, 5, NULL);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create broker task");
        vQueueDelete(broker_ctx.broker_queue);
        return false;
    }

    broker_ctx.initialized = true;
    ESP_LOGI(TAG, "Broker initialized successfully");
    return true;
}

bool broker_register_task(const char* task_name) {
    if (!broker_ctx.initialized || !task_name) {
        return false;
    }

    // Verifica se il task è già registrato
    for (int i = 0; i < MAX_TASKS; i++) {
        if (broker_ctx.tasks[i].in_use && 
            strcmp(broker_ctx.tasks[i].name, task_name) == 0) {
            return true;
        }
    }

    // Trova uno slot libero
    for (int i = 0; i < MAX_TASKS; i++) {
        if (!broker_ctx.tasks[i].in_use) {
            // Crea una nuova coda per il task
            QueueHandle_t queue = xQueueCreate(BROKER_QUEUE_SIZE, sizeof(broker_message_t));
            if (!queue) {
                ESP_LOGE(TAG, "Failed to create queue for task %s", task_name);
                return false;
            }

            // Registra il task
            strncpy(broker_ctx.tasks[i].name, task_name, MAX_TASK_NAME_LENGTH - 1);
            broker_ctx.tasks[i].queue = queue;
            broker_ctx.tasks[i].in_use = true;
            
            ESP_LOGI(TAG, "Task %s registered successfully", task_name);
            return true;
        }
    }

    ESP_LOGE(TAG, "No free slots for new task registration");
    return false;
}

bool broker_unregister_task(const char* task_name) {
    if (!broker_ctx.initialized || !task_name) {
        return false;
    }

    for (int i = 0; i < MAX_TASKS; i++) {
        if (broker_ctx.tasks[i].in_use && 
            strcmp(broker_ctx.tasks[i].name, task_name) == 0) {
            // Elimina la coda del task
            vQueueDelete(broker_ctx.tasks[i].queue);
            
            // Resetta lo slot
            memset(&broker_ctx.tasks[i], 0, sizeof(task_info_t));
            
            ESP_LOGI(TAG, "Task %s unregistered successfully", task_name);
            return true;
        }
    }

    return false;
}

bool broker_send_message(const char* source, const char* destination, 
                        const uint8_t* data, size_t length, uint8_t type) {
    if (!broker_ctx.initialized || !source || !destination || 
        !data || length > MAX_MESSAGE_SIZE) {
        return false;
    }

    broker_message_t message = {0};
    strncpy(message.source, source, MAX_TASK_NAME_LENGTH - 1);
    strncpy(message.destination, destination, MAX_TASK_NAME_LENGTH - 1);
    memcpy(message.data, data, length);
    message.data_length = length;
    message.message_type = type;

    if (xQueueSend(broker_ctx.broker_queue, &message, 0) != pdPASS) {
        ESP_LOGW(TAG, "Failed to send message from %s to %s", source, destination);
        return false;
    }

    return true;
}

bool broker_receive_message(const char* task_name, broker_message_t* message, 
                          TickType_t wait_ticks) {
    if (!broker_ctx.initialized || !task_name || !message) {
        return false;
    }

    // Trova la coda del task
    QueueHandle_t task_queue = NULL;
    for (int i = 0; i < MAX_TASKS; i++) {
        if (broker_ctx.tasks[i].in_use && 
            strcmp(broker_ctx.tasks[i].name, task_name) == 0) {
            task_queue = broker_ctx.tasks[i].queue;
            break;
        }
    }

    if (!task_queue) {
        ESP_LOGW(TAG, "Task %s not found", task_name);
        return false;
    }

    // Ricevi il messaggio dalla coda del task
    if (xQueueReceive(task_queue, message, wait_ticks) != pdPASS) {
        return false;
    }

    return true;
}

void broker_deinit(void) {
    if (!broker_ctx.initialized) {
        return;
    }

    // Elimina tutte le code dei task
    for (int i = 0; i < MAX_TASKS; i++) {
        if (broker_ctx.tasks[i].in_use) {
            vQueueDelete(broker_ctx.tasks[i].queue);
        }
    }

    // Elimina la coda del broker
    vQueueDelete(broker_ctx.broker_queue);

    // Resetta il contesto
    memset(&broker_ctx, 0, sizeof(broker_ctx));
    
    ESP_LOGI(TAG, "Broker deinitialized");
}