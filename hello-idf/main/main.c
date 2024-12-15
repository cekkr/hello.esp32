#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include "driver/gpio.h"
#include "driver/spi_common.h"
#include "driver/uart_vfs.h"
#include "hal/uart_ll.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_trace.h"

// Watchdog
#include "esp_task_wdt.h"
#include "rtc_wdt.h"

// Touch Screen
#include "lcd.h"
#include "gui.h"
#include "pic.h"
#include "xpt2046.h"

// Constants
static const char *TAG = "HELLOESP";
#define SD_MOUNT_POINT "/sdcard"
#define MAX_FILENAME 256

// General functions
#include "io.h"
#include "esp_exception.h"
#include "device.h"

// CMDs
#include "cmd.h"


///
/// SD
///
#define SD_SCK  18
#define SD_MISO 19
#define SD_MOSI 23
#define SD_CS   5

#define SPI_DMA_CHAN    1

#define CONFIG_XPT2046_ENABLE_DIFF_BUS 1

#include "sdcard.h"
#include "serial.h"

///
/// Touch Screen
///

#define CONFIG_XPT_MISO_GPIO   39
#define CONFIG_XPT_CS_GPIO     33
#define CONFIG_XPT_IRQ_GPIO    36
#define CONFIG_XPT_SCLK_GPIO   25
#define CONFIG_XPT_MOSI_GPIO   32

static void Draw(void *pvParameters)
{
    WATCHDOG_ADD

	uint16_t CurrentColor = BLUE;
	while (1){
		if(xpt2046_read()){
            ESP_LOGI(TAG,"Touch: %d, %d", TouchX, TouchY);

			if(TouchY<=30 && TouchX<=30){
                LCD_ShowString(10,80,WHITE,BLACK,10,"Reading SD",0);
                mostra_info_sd(SD_MOUNT_POINT);
                LCD_ShowString(10,60,WHITE,BLACK,10,"Read.",0);

				CurrentColor = BLUE;
			}else if(TouchY<=30 && TouchX>30 && TouchX<60){
				CurrentColor = BROWN;
			}else if(TouchY<=30 && TouchX>60 && TouchX<90){
				CurrentColor = GREEN;
			}else if(TouchY<=30 && TouchX>90 && TouchX<120){
				CurrentColor = GBLUE;
			}else if(TouchY<=30 && TouchX>120 && TouchX<150){
				CurrentColor = RED;
			}else if(TouchY<=30 && TouchX>150 && TouchX<180){
				CurrentColor = MAGENTA;
			}else if(TouchY<=30 && TouchX>180 && TouchX<210){
				CurrentColor = YELLOW;
			}else if(TouchY<=30 && TouchX>210 && TouchX < 240){
				LCD_DrawFillRectangle(0,31,240,320,WHITE);
			}
			else{
				LCD_DrawPoint1(TouchX,TouchY,CurrentColor);//画点 
			}
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);

	}

    WATCHDOG_END
	vTaskDelete(NULL);
}
void init_tft(void)
{
	esp_err_t ret;
	ESP_LOGI(TAG, "APP Start......");
	Init_LCD(WHITE);
	//初始化 XPT2046
	xpt2046_init();
	LCD_Set_Orientation(LCD_DISPLAY_ORIENTATION_LANDSCAPE_INVERTED);// 纵向翻转
	
    //TP_Adjust(); // Serve per calibrare lo schermo
    
	// 实心矩形
	LCD_DrawFillRectangle(0,0,30,30,BLUE);
	LCD_DrawFillRectangle(30,0,60,30,BROWN);
	LCD_DrawFillRectangle(60,0,90,30,GREEN);
	LCD_DrawFillRectangle(90,0,120,30,GBLUE);
	LCD_DrawFillRectangle(120,0,150,30,RED);
	LCD_DrawFillRectangle(150,0,180,30,MAGENTA);
	LCD_DrawFillRectangle(180,0,210,30,YELLOW);
	LCD_DrawRectangle(210,0,240,30,RED);
	LCD_ShowString(215,9,WHITE,BLACK,16,"Cle",0);
	LCD_DrawFillRectangle(0,31,240,320,WHITE);
	xTaskCreate(&Draw, "Draw", 4096, NULL, 5, NULL);
}

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
        .intr_flags = ESP_INTR_FLAG_IRAM
    };

    // Add flags to initialize SPI without DMA
    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_config, SPI_DMA_DISABLED);
}

void device_info(){
    uint32_t flash_size;
    esp_flash_get_size(NULL, &flash_size);
    ESP_LOGI(TAG, "Flash size: %d bytes\n", flash_size);
}

static const int UART_BUFFER_SIZE = 1024;  // Cambiato da bool a int

void init_uart() {
    uart_config_t uart_config = {
        .baud_rate = 115200,
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

void enable_log_debug(){
    esp_log_level_set("*", ESP_LOG_DEBUG);
}

void app_main(void) {    
    //handle_watchdog();
    WATCHDOG_ADD

    device_info();    

    init_error_handling();
    init_custom_logging();
    enable_log_debug();
    //heap_caps_malloc_extmem_enable(20); // no PSRAM available, ergo useless

    if(false){
        //ESP_ERROR_CHECK(heap_trace_init_standalone(heap_trace_records, HEAP_TRACE_ALL));
        //ESP_ERROR_CHECK(heap_trace_start(HEAP_TRACE_LEAKS));
    }    

    // Inizializzazione della seriale
    init_uart();

    ESP_LOGI(TAG, "\nStarting SD card test...\n");
    init_sd_card(); 

	// Avvia il thread di gestione seriale
    ESP_LOGI(TAG, "\nStarting serial handler...\n");
    start_serial_handler();

    //init_spi(); 

    ESP_LOGI(TAG, "Init TFT\n");
    init_tft();      

    #if ENABLE_WATCHDOG
    esp_task_wdt_add(NULL);
    #endif 

    while(1){        
        WATCHDOG_RESET
        reset_wdt();
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
    //__real_esp_panic_handler(info);
}

////
////
////
