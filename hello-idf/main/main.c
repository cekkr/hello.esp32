#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include "driver/gpio.h"
#include "driver/spi_common.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// Touch Screen
#include "lcd.h"
#include "gui.h"
#include "pic.h"
#include "xpt2046.h"

static const char *TAG = "hello_esp";

///
/// SD
///
#define SD_SCK  18
#define SD_MISO 19
#define SD_MOSI 23
#define SD_CS   5

#define MOUNT_POINT "/sdcard"
#define SPI_DMA_CHAN    1

#define CONFIG_XPT2046_ENABLE_DIFF_BUS 1

#include "sdcard.h"

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
	uint16_t CurrentColor = BLUE;
	while (1){
		if(xpt2046_read()){
			if(TouchY<=30 && TouchX<=30){
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
	vTaskDelete(NULL);
}
void init_tft(void)
{
	esp_err_t ret;
	ESP_LOGI(TAG, "APP Start......");
	Init_LCD(WHITE);
	//初始化 XPT2046
	xpt2046_init();
	LCD_Set_Orientation(LCD_DISPLAY_ORIENTATION_LANDSCAPE);// 纵向翻转
	
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
	while(1){
        mostra_info_sd("/sdcard");
		vTaskDelay(1000 / portTICK_PERIOD_MS);
	}
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

void app_main(void) {
    esp_task_wdt_delete(NULL);

    init_spi();

    printf("\nStarting SD card test...\n");
    init_sd_card();

    printf("Init TFT\n");
    init_tft();        
}