#include "driver/uart.h"
#include "he_defines.h"

#if SERIAL_WRITER_BROKER_ENABLE
#include "he_task_broker.h"
#endif

void serial_write(const char* data, size_t len){    
    #if SERIAL_WRITER_BROKER_ENABLE
    if(serial_writer_broker_connected){
        int tries = 0;
        while(!broker_send_message(serial_writer_sender_name, serial_writer_broker_name, (const uint8_t*)data, len, BROKER_MSG_TYPE_STRING))
        {
            if(tries++ > SERIAL_MUTEX_MAX_TRIES) break;
            vTaskDelay(pdMS_TO_TICKS(SERIAL_WRITER_WAIT_MS));
        }
        return;
    }
    #endif

    uart_write_bytes(UART_NUM_0, data, len);
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
}

void safe_printf(const char* format, size_t length, ...) {          
    #if SERIAL_WRITER_BROKER_ENABLE

    va_list args;
    va_list args_copy;
    
    // Prima chiamata per determinare la lunghezza necessaria
    va_start(args, length);
    va_copy(args_copy, args);
    int required_length = vsnprintf(NULL, 0, format, args) + 1; // +1 per il terminatore
    va_end(args);
    
    // Allocazione della memoria
    char* buffer = (char*)malloc(required_length);
    if (buffer == NULL) {
        length = 0;
        return;
    }
    
    // Seconda chiamata per effettuare la formattazione
    length = vsnprintf(buffer, required_length, format, args_copy);
    va_end(args_copy);

    serial_write(buffer, length);

    #else
    bool monitor_disabled = disable_monitor;
    disable_monitor = true;

    if(serial_mutex){
        int max_tries = 0;
        while(xSemaphoreTake(serial_mutex, pdMS_TO_TICKS(SERIAL_SEMAPHORE_WAIT_MS)) != pdTRUE) {
            if(max_tries++ > SERIAL_MUTEX_MAX_TRIES) {
                if(monitor_disabled) disable_monitor = monitor_disabled;
                return;
            }
        }
    }  

    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);    
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
    vTaskDelay(pdMS_TO_TICKS(1));

    if(serial_mutex) xSemaphoreGive(serial_mutex);    
    if(monitor_disabled) disable_monitor = monitor_disabled;
    #endif    
}
