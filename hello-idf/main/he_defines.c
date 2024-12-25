#include "driver/uart.h"

#include "he_defines.h"

void safe_printf(const char* format, ...) {
    if(serial_mutex){
        int max_tries = 0;
        while(xSemaphoreTake(serial_mutex, pdMS_TO_TICKS(SERIAL_SEMAPHORE_WAIT_MS)) != pdTRUE) {
            if(max_tries++ > SERIAL_MUTEX_MAX_TRIES) return;

            vTaskDelay(pdMS_TO_TICKS(SERIAL_SEMAPHORE_WAIT_MS));
        }
    }
    
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    
    uart_wait_tx_done(UART_NUM_0, portMAX_DELAY);
    if(serial_mutex) xSemaphoreGive(serial_mutex);
    //vTaskDelay(pdMS_TO_TICKS(10));
}
