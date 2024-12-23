// task_broker.h
#ifndef TASK_BROKER_H
#define TASK_BROKER_H

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <string.h>
#include <stdbool.h>

#define MAX_TASKS 10
#define MAX_TASK_NAME_LENGTH 16
#define MAX_MESSAGE_SIZE 64
#define BROKER_QUEUE_SIZE 20

// Struttura del messaggio
typedef struct {
    char source[MAX_TASK_NAME_LENGTH];      // Nome task mittente
    char destination[MAX_TASK_NAME_LENGTH];  // Nome task destinatario
    uint8_t data[MAX_MESSAGE_SIZE];         // Dati del messaggio
    size_t data_length;                     // Lunghezza dei dati
    uint8_t message_type;                   // Tipo di messaggio
} broker_message_t;

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
