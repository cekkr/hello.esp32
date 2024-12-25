// task_broker.h
#ifndef TASK_BROKER_H
#define TASK_BROKER_H

#include "he_defines.h"

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <string.h>
#include <stdbool.h>

// Struttura del messaggio
typedef struct {
    char source[MAX_TASK_NAME_LENGTH];      // Nome task mittente
    char destination[MAX_TASK_NAME_LENGTH];  // Nome task destinatario
    uint8_t data[MAX_MESSAGE_SIZE];         // Dati del messaggio
    size_t data_length;                     // Lunghezza dei dati
    uint8_t message_type;                   // Tipo di messaggio
} broker_message_t;

#define BROKER_MSG_TYPE_STRING 1

// API pubbliche
bool broker_init(void);
bool broker_register_task(const char* task_name);
bool broker_unregister_task(const char* task_name);
bool broker_send_message(const char* source, const char* destination, 
                        const uint8_t* data, size_t length, uint8_t type);
bool broker_receive_message(const char* task_name, broker_message_t* message, 
                          TickType_t wait_ticks);
void broker_deinit(void);

#endif // TASK_BROKER_H

/* Example usage:

// main.c
#include "task_broker.h"

// Task di esempio che invia messaggi
void sender_task(void *pvParameters) {
    // Registra il task
    broker_register_task("sender");
    
    uint8_t counter = 0;
    while(1) {
        // Invia un messaggio al receiver
        broker_send_message("sender", "receiver", &counter, sizeof(counter), 1);
        counter++;
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

// Task di esempio che riceve messaggi
void receiver_task(void *pvParameters) {
    // Registra il task
    broker_register_task("receiver");
    
    broker_message_t message;
    while(1) {
        // Ricevi messaggi
        if (broker_receive_message("receiver", &message, portMAX_DELAY)) {
            printf("Ricevuto messaggio da %s: %d\n", 
                   message.source, message.data[0]);
        }
    }
}

void app_main(void) {
    // Inizializza il broker
    broker_init();
    
    // Crea i task
    xTaskCreate(sender_task, "sender_task", 2048, NULL, 5, NULL);
    xTaskCreate(receiver_task, "receiver_task", 2048, NULL, 5, NULL);
}

*/