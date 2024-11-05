Per far funzionare contemporaneamente due dispositivi SPI (LCD e SD card) sullo stesso ESP32, dovrai utilizzare due bus SPI differenti. Ecco come strutturare il codice:

```c
#include "driver/spi_master.h"
#include "esp_log.h"

// Definizione dei PIN per LCD
#define LCD_MISO GPIO_NUM_19
#define LCD_MOSI GPIO_NUM_23
#define LCD_CLK  GPIO_NUM_18
#define LCD_CS   GPIO_NUM_5
#define LCD_DC   GPIO_NUM_21

// Definizione dei PIN per SD Card (su bus SPI differente)
#define SD_MISO  GPIO_NUM_12
#define SD_MOSI  GPIO_NUM_13
#define SD_SCK   GPIO_NUM_14
#define SD_CS    GPIO_NUM_15

static const char *TAG = "SPI_INIT";

esp_err_t init_spi_buses(void) {
    esp_err_t ret;

    // Configurazione bus SPI per LCD (VSPI / SPI3)
    spi_bus_config_t lcd_bus_cfg = {
        .miso_io_num = LCD_MISO,
        .mosi_io_num = LCD_MOSI,
        .sclk_io_num = LCD_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = PARALLEL_LINES*320*2+8
    };
    
    // Configurazione device SPI per LCD
    spi_device_interface_config_t lcd_dev_cfg = {
        .clock_speed_hz = 30*1000*1000,           // Clock 30 MHz
        .mode = 0,                                // Modalità SPI 0
        .spics_io_num = LCD_CS,                   // CS pin
        .queue_size = 7,                          // Dimensione coda
        .pre_cb = lcd_spi_pre_transfer_callback,  // Callback pre-transfer
    };

    // Inizializzazione bus SPI per LCD (VSPI / SPI3)
    ret = spi_bus_initialize(VSPI_HOST, &lcd_bus_cfg, LCD_DMA_CHAN);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Errore inizializzazione bus LCD SPI: %s", esp_err_to_name(ret));
        return ret;
    }

    // Aggiungi il device LCD al bus
    spi_device_handle_t lcd_spi;
    ret = spi_bus_add_device(VSPI_HOST, &lcd_dev_cfg, &lcd_spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Errore aggiunta device LCD: %s", esp_err_to_name(ret));
        return ret;
    }

    // Configurazione bus SPI per SD Card (HSPI / SPI2)
    spi_bus_config_t sd_bus_cfg = {
        .mosi_io_num = SD_MOSI,
        .miso_io_num = SD_MISO,
        .sclk_io_num = SD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4000,
        .flags = SPICOMMON_BUSFLAG_MASTER | 
                SPICOMMON_BUSFLAG_GPIO_PINS |
                SPICOMMON_BUSFLAG_SCLK |
                SPICOMMON_BUSFLAG_MISO |
                SPICOMMON_BUSFLAG_MOSI,
        .intr_flags = ESP_INTR_FLAG_IRAM
    };

    // Inizializzazione bus SPI per SD Card (HSPI / SPI2)
    ret = spi_bus_initialize(HSPI_HOST, &sd_bus_cfg, SD_DMA_CHAN);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Errore inizializzazione bus SD Card SPI: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "Inizializzazione SPI completata con successo");
    return ESP_OK;
}

```

I punti chiave per far funzionare entrambi i dispositivi sono:

1. **Usa Bus SPI Differenti**:
   - LCD su VSPI_HOST (SPI3)
   - SD Card su HSPI_HOST (SPI2)

2. **PIN Separati**:
   - Ogni dispositivo deve avere i propri PIN dedicati
   - Ho fornito un esempio di configurazione, ma puoi modificare i numeri dei PIN in base al tuo hardware

3. **DMA Channels**:
   - Usa canali DMA differenti per ogni bus
   - Per esempio:
     ```c
     #define LCD_DMA_CHAN 1
     #define SD_DMA_CHAN 2
     ```

4. **Gestione degli Errori**:
   - Il codice include controlli degli errori per ogni operazione di inizializzazione

Per utilizzare questo codice:

1. Modifica i numeri dei PIN secondo il tuo setup hardware
2. Chiama `init_spi_buses()` durante l'inizializzazione
3. Assicurati che i PIN scelti non siano utilizzati per altre funzioni

Se hai bisogno di modificare qualche parametro specifico o hai domande sulla configurazione dei PIN, fammi sapere!