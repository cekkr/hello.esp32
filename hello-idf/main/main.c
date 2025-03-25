#include "driver/uart.h"     // Per UART_NUM_0 e altre costanti UART

////////////////////////////////
#include "he_defines.h"
#include "he_settings.h"

// General functions
#include "he_esp_exception.h"
#include "he_task_broker.h"
#include "he_device.h"
#include "he_monitor.h"

// CMDs
#include "he_screen.h"
#include "he_sdcard.h"
#include "he_serial.h"
#include "he_device.h"

// GDB Debug
#include "esp_gdbstub.h"

///
/// General
///

void init_spi(){
    // Before SPI initialization
    spi_bus_config_t bus_config = {
        //.mosi_io_num = MOSI_PIN,
        //.miso_io_num = -1,  // -1 if not used
        //.sclk_io_num = SCK_PIN,
        //.quadwp_io_num = -1,
        //.quadhd_io_num = -1,
        //.max_transfer_sz = 16*320*2
        .flags = SPICOMMON_BUSFLAG_MASTER | 
                SPICOMMON_BUSFLAG_GPIO_PINS |
                SPICOMMON_BUSFLAG_SCLK |
                SPICOMMON_BUSFLAG_MISO |
                SPICOMMON_BUSFLAG_MOSI,
        #if ENABLE_INTR_FLAG_IRAM_SPI
        .intr_flags =  ESP_INTR_FLAG_IRAM // or Component config -> Driver configurations -> SPI configuration -> (x) Place SPI driver ISR function into IRAM        
        #endif
    };

    // Add flags to initialize SPI without DMA
    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_config, SPI_DMA_DISABLED);
}

static const int UART_BUFFER_SIZE = 1024;  // Cambiato da bool a int

void init_uart() {    
    uart_config_t uart_config = {
        .baud_rate = SERIAL_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        //.source_clk = UART_SCLK_REF_TICK,
        //.rx_flow_ctrl_thresh = 122
    };
    
    // Configura la UART
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, UART_BUFFER_SIZE, UART_BUFFER_SIZE, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));

    // Reindirizza stdout alla UART
    esp_vfs_dev_uart_use_driver(UART_NUM_0);
    esp_vfs_dev_uart_port_set_rx_line_endings(UART_NUM_0, ESP_LINE_ENDINGS_CR);
    esp_vfs_dev_uart_port_set_tx_line_endings(UART_NUM_0, ESP_LINE_ENDINGS_CRLF);

    // Inizializza il VFS per UART
    const uart_dev_t* uart = UART_LL_GET_HW(UART_NUM_0);
    esp_vfs_dev_uart_register();

    // Imposta i buffer standard
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
}

////
////
////

void app_main(void) { 
    esp_gdbstub_init();
    
    settings_t* settings = get_main_settings();
    *settings = settings_default;

    settings->_serial_mutex = xSemaphoreCreateMutex();

    // Init task broker
    broker_init();

    // Inizializzazione della seriale
    init_uart();

    // Init watchdog
    handle_watchdog();
    //WATCHDOG_ADD

    device_info();    

    init_error_handling();
    //init_custom_logging(); // this crash everything
    enable_log_debug();

    //heap_caps_malloc_extmem_enable(20); // no PSRAM available, ergo useless       

    ////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////

    ESP_LOGI(TAG, "\nStarting SD card test...\n");
    if(init_sd_card()){
        settings->_sd_card_initialized = true;
        load_global_settings();
    }
    else {
        ESP_LOGE(TAG, "Failed to initialize SD card");
    }

    // Start tasks monitor
    #if ENABLE_MONITOR
    init_tasksMonitor();
    #endif

	// Avvia il thread di gestione seriale
    ESP_LOGI(TAG, "\nStarting serial handler...\n");
    start_serial_handler();

    ESP_LOGI(TAG, "\nInit SPI...\n");
    init_spi(); 

    ESP_LOGI(TAG, "Init TFT\n");
    init_tft();      

    while(1){        
        //WATCHDOG_RESET
		vTaskDelay(pdMS_TO_TICKS(100));
	}
}

////
////
////

/* Declare the real panic handler function. We'll be able to call it after executing our custom code */
void __real_esp_panic_handler(void*);

/* This function will be considered the esp_panic_handler to call in case a panic occurs */
void __wrap_esp_panic_handler (void* info) {
    /* Custom code, count the number of panics or simply print a message */
    //esp_rom_printf("Panic has been triggered by the program!\n");
    ESP_LOGE(TAG, "Kernel Panic Handler triggered");
    
    //todo: print info
    vTaskDelay(pdMS_TO_TICKS(100));

    esp_backtrace_print(100);    

    vTaskDelay(pdMS_TO_TICKS(1000));

    /* Call the original panic handler function to finish processing this error (creating a core dump for example...) */
    __real_esp_panic_handler(info);
}

///

void shutdown_handler(void) {
    ESP_LOGE("SHUTDOWN", "Sistema in fase di riavvio!");
    // Puoi salvare informazioni importanti qui
}

////
////
////
