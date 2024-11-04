#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/sdmmc_types.h"
#include "driver/sdspi_host.h"
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
/// Touch Screen
///
#define CONFIG_XPT_MISO_GPIO   39
#define CONFIG_XPT_CS_GPIO     33
#define CONFIG_XPT_IRQ_GPIO    36
#define CONFIG_XPT_SCLK_GPIO   25
#define CONFIG_XPT_MOSI_GPIO   32
#define CONFIG_XPT_ACCURACY    10

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
	LCD_Set_Orientation(LCD_DISPLAY_ORIENTATION_PORTRAIT_INVERTED);// 纵向翻转
	TP_Adjust();
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
		vTaskDelay(1000 / portTICK_PERIOD_MS);
	}
}


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

void init_sd_pins() {
    printf("Initializing SD pins with pull-ups...\n");
    
    // Configura tutti i pin con pull-up
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT_OUTPUT,
        .pin_bit_mask = ((1ULL<<SD_SCK) | (1ULL<<SD_MOSI) | (1ULL<<SD_CS)),
        .pull_down_en = 0,
        .pull_up_en = 1
    };
    gpio_config(&io_conf);

    // MISO configurato separatamente
    gpio_config_t miso_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL<<SD_MISO),
        .pull_down_en = 0,
        .pull_up_en = 1
    };
    gpio_config(&miso_conf);

    // Imposta esplicitamente i pull-up
    gpio_set_pull_mode(SD_MISO, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_MOSI, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_SCK, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SD_CS, GPIO_PULLUP_ONLY);

    // Imposta CS alto (deselezionato)
    gpio_set_direction(SD_CS, GPIO_MODE_OUTPUT);
    gpio_set_level(SD_CS, 1);

    // Aspetta che le tensioni si stabilizzino
    vTaskDelay(pdMS_TO_TICKS(100));

    printf("Testing SD pins state:\n");
    printf("CS (GPIO%d) Level: %d\n", SD_CS, gpio_get_level(SD_CS));
    printf("MISO (GPIO%d) Level: %d\n", SD_MISO, gpio_get_level(SD_MISO));
    printf("MOSI (GPIO%d) Level: %d\n", SD_MOSI, gpio_get_level(SD_MOSI));
    printf("SCK (GPIO%d) Level: %d\n", SD_SCK, gpio_get_level(SD_SCK));
    
    // Test di toggle dei pin per verificare il funzionamento
    printf("\nTesting pin toggles:\n");
    for (int i = 0; i < 3; i++) {
        gpio_set_level(SD_CS, 0);
        gpio_set_level(SD_MOSI, 0);
        gpio_set_level(SD_SCK, 0);
        printf("Pins Low - MISO: %d\n", gpio_get_level(SD_MISO));
        vTaskDelay(pdMS_TO_TICKS(100));
        
        gpio_set_level(SD_CS, 1);
        gpio_set_level(SD_MOSI, 1);
        gpio_set_level(SD_SCK, 1);
        printf("Pins High - MISO: %d\n", gpio_get_level(SD_MISO));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    
    // Ritorna CS alto per inizializzazione
    gpio_set_level(SD_CS, 1);
    vTaskDelay(pdMS_TO_TICKS(100));
}

void init_sd_card() {
    esp_err_t ret;
    
    // Inizializza i pin
    init_sd_pins();
    
    printf("\nInitializing SPI bus...\n");
    spi_bus_config_t bus_cfg = {
        .mosi_io_num = SD_MOSI,
        .miso_io_num = SD_MISO,
        .sclk_io_num = SD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4000,
        .flags = SPICOMMON_BUSFLAG_MASTER,
    };

    // Inizializza il bus SPI con frequenza molto bassa
    ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CHAN);
    if (ret != ESP_OK) {
        printf("Failed to initialize bus. Error: %s\n", esp_err_to_name(ret));
        return;
    }

    printf("SPI bus initialized successfully\n");

    // Configurazione host con frequenza molto bassa per il debug
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SPI2_HOST;
    host.max_freq_khz = 400; // Ridotto a 400KHz per il debug

    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs = SD_CS;
    slot_config.host_id = host.slot;

    printf("\nMounting SD card...\n");
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };

    sdmmc_card_t *card;
    ret = esp_vfs_fat_sdspi_mount(MOUNT_POINT, &host, &slot_config, &mount_config, &card);

    if (ret != ESP_OK) {
        printf("\nMount failed with error: %s (0x%x)\n", esp_err_to_name(ret), ret);
        printf("Debug info:\n");
        printf("1. Check physical connections:\n");
        printf("   - CS   -> GPIO%d\n", SD_CS);
        printf("   - MISO -> GPIO%d\n", SD_MISO);
        printf("   - MOSI -> GPIO%d\n", SD_MOSI);
        printf("   - SCK  -> GPIO%d\n", SD_SCK);
        printf("2. Verify SD card is properly inserted\n");
        printf("3. Check if card works in a computer\n");
        printf("4. Verify 3.3V power supply\n");
        printf("5. Add 10kΩ pull-up resistors if not present\n");
        return;
    }

    printf("\nSD card mounted successfully!\n");
    printf("Card info:\n");
    printf("Name: %s\n", card->cid.name);
    printf("Type: %s\n", (card->ocr & (1 << 30)) ? "SDHC/SDXC" : "SDSC");
    printf("Speed: %s\n", (card->csd.tr_speed > 25000000) ? "High Speed" : "Default Speed");
    printf("Size: %lluMB\n", ((uint64_t)card->csd.capacity) * card->csd.sector_size / (1024 * 1024));
}

void app_main(void) {
    esp_task_wdt_delete(NULL);

    printf("\nStarting SD card test...\n");
    init_sd_card();

    init_tft();
}