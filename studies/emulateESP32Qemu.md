# Guida all'emulazione ESP32 con QEMU su macOS

Questa guida ti mostrerà come configurare un ambiente di emulazione per ESP32 con supporto a LCD, touch e scheda SD utilizzando QEMU su macOS.

## Prerequisiti

Prima di iniziare, assicurati di avere installato:

- Homebrew (per l'installazione dei pacchetti)
- Git
- Python 3.8 o superiore
- CMake

## 1. Installazione degli strumenti necessari

Apri il terminale e installa i pacchetti richiesti:

```bash
# Installa Homebrew se non lo hai già
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Installa i pacchetti necessari
brew install cmake ninja dfu-util
brew install python3

brew install gnutls
brew install pkg-config

# Installa QEMU con supporto per ESP32
brew install qemu
```

## 2. Configurazione dell'ambiente ESP-IDF

ESP-IDF è il framework di sviluppo ufficiale di Espressif per ESP32. Ecco come configurarlo:

```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
git checkout release/v4.4  # Puoi scegliere una versione più recente

# Installa gli strumenti ESP-IDF
./install.sh
```

## 3. Installazione di ESP-QEMU

ESP-QEMU è una versione modificata di QEMU con supporto specifico per i chip ESP32:

```bash
cd ~/esp
git clone https://github.com/espressif/qemu.git
cd qemu
git submodule update --init --recursive
git checkout esp-develop  # Usa il branch di sviluppo Espressif

# Configura e compila QEMU per ESP32
mkdir build
cd build
../configure --target-list=xtensa-softmmu \
             --enable-gcrypt \
             --enable-debug \
             --enable-sdl \
             --enable-curses
make -j8  # Sostituisci 8 con il numero di core disponibili

# macOS configuration
# substitute 3.8.4 with your brew package version

# Imposta le variabili di ambiente per gli include path
export CFLAGS="-I/opt/homebrew/Cellar/gnutls/3.8.4/include $CFLAGS"
export CPPFLAGS="-I/opt/homebrew/Cellar/gnutls/3.8.4/include $CPPFLAGS"

# Imposta anche la variabile per i library path se necessario
export LDFLAGS="-L/opt/homebrew/Cellar/gnutls/3.8.4/lib $LDFLAGS"

# Aggiorna anche PKG_CONFIG_PATH
export PKG_CONFIG_PATH="/opt/homebrew/Cellar/gnutls/3.8.4/lib/pkgconfig:$PKG_CONFIG_PATH"

../configure (...)

make -j8
```

## 4. Configurazione del supporto per LCD, touch, SD e PSRAM

Per emulare l'hardware specifico, dobbiamo configurare i dispositivi periferici:

### 4.1. Configurazione LCD

Per emulare un display LCD, è necessario configurare il driver SPI per il display:

```bash
# Creiamo un file di configurazione QEMU per LCD
cat > ~/esp/qemu_esp32_lcd.cfg << 'EOF'
[machine]
spi0.device = "esp32.spi"
spi0.lcd_device = "ili9341"
spi0.width = 320
spi0.height = 240
spi0.cs_pin = 5
spi0.dc_pin = 4
spi0.rst_pin = 15
EOF
```

### 4.2. Configurazione Touch

Per il supporto touch, configuriamo il driver touch capacitivo:

```bash
# Aggiungiamo la configurazione touch al file
cat >> ~/esp/qemu_esp32_lcd.cfg << 'EOF'
[touch]
device = "ft6x36"
i2c_address = 0x38
irq_pin = 39
width = 320
height = 240
EOF
```

### 4.3. Configurazione SD Card

Per emulare una scheda SD:

```bash
# Creiamo una immagine di file system per la SD
cd ~/esp/
dd if=/dev/zero of=sdcard.img bs=1M count=32

# Aggiungiamo la configurazione SD al file
cat >> ~/esp/qemu_esp32_lcd.cfg << 'EOF'
[sd]
device = "sdspi"
cs_pin = 13
wp_pin = -1
image = "sdcard.img"
EOF
```

### 4.4. Configurazione PSRAM (opzionale)

Per abilitare l'emulazione della PSRAM (Pseudo Static RAM):

```bash
# Aggiungiamo la configurazione PSRAM al file
cat >> ~/esp/qemu_esp32_lcd.cfg << 'EOF'
[psram]
enabled = true
size = 4194304  # 4MB di PSRAM (dimensione in byte)
EOF
```

L'emulazione della PSRAM può essere abilitata o disabilitata cambiando il valore di `enabled` tra `true` e `false`. Puoi anche modificare la dimensione della PSRAM cambiando il valore di `size` (in byte). Il valore predefinito di 4MB è tipico per molte schede ESP32 con PSRAM.

## 5. Creazione di un progetto di esempio

Creiamo un progetto di esempio che utilizza LCD, touch e SD card:

```bash
cd ~/esp
. ./esp-idf/export.sh  # Carica le variabili d'ambiente ESP-IDF

# Clona un progetto di esempio che usa LCD, touch e SD
git clone https://github.com/espressif/esp-idf-template.git esp32-lcd-touch-sd-demo
cd esp32-lcd-touch-sd-demo
```

## 6. Configurazione del progetto

Modifichiamo la configurazione del progetto per abilitare le periferiche:

```bash
# Configura il progetto
idf.py menuconfig
```

Nel menu di configurazione:
1. Vai a "Component config" → "ESP32-specific" → abilita "Support for external, SPI-connected RAM"
2. Vai a "Component config" → "ESP32-specific" → "Support for external, SPI-connected RAM" → abilita "Initialize SPI RAM during startup"
3. Vai a "Component config" → "ESP32-specific" → "Support for external, SPI-connected RAM" → abilita "Enable SPI RAM allocatable with heap_caps_malloc"
4. Vai a "Component config" → "Driver configurations" → "SPI configuration" → abilita "SPI Master"
5. Configura "Component config" → "FAT Filesystem support" → abilita "Long filename support" e "SPI Disk Support"

## 7. Configurazione del codice di esempio

Creiamo un'applicazione di esempio che testa LCD, touch e SD:

```bash
# Sostituisci il file main con il nostro esempio
cat > main/main.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "driver/sdspi_host.h"
#include "sdmmc_cmd.h"

// Display includes
#include "ili9341.h"
#include "ft6x36.h"
#include "esp_heap_caps.h"

#define TAG "MAIN"

// LCD Pin definitions
#define LCD_SPI_HOST    HSPI_HOST
#define LCD_CS_PIN      5
#define LCD_DC_PIN      4
#define LCD_RST_PIN     15
#define LCD_BL_PIN      2

// Touch Pin definitions
#define TOUCH_I2C_PORT  I2C_NUM_0
#define TOUCH_I2C_SDA   21
#define TOUCH_I2C_SCL   22
#define TOUCH_IRQ_PIN   39

// SD Card Pin definitions
#define SD_CS_PIN       13
#define SD_MOSI_PIN     23
#define SD_MISO_PIN     19
#define SD_CLK_PIN      18

static void init_lcd(void)
{
    // Initialize display
    spi_device_handle_t spi;
    ili9341_init(LCD_SPI_HOST, LCD_CS_PIN, LCD_DC_PIN, LCD_RST_PIN, LCD_BL_PIN, &spi);
    ili9341_fill_screen(spi, ILI9341_BLACK);
    ili9341_draw_string(spi, 10, 10, "ESP32 LCD Test", ILI9341_WHITE, ILI9341_BLACK, 2);
    ESP_LOGI(TAG, "LCD initialized");
}

static void init_touch(void)
{
    // Initialize touch
    ft6x36_init(TOUCH_I2C_PORT, TOUCH_I2C_SDA, TOUCH_I2C_SCL, TOUCH_IRQ_PIN);
    ESP_LOGI(TAG, "Touch initialized");
}

static void init_sd_card(void)
{
    esp_err_t ret;
    sdmmc_card_t *card;
    
    // Options for mounting the filesystem
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = true,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };
    
    // SD card config
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    sdspi_slot_config_t slot_config = SDSPI_SLOT_CONFIG_DEFAULT();
    slot_config.gpio_cs = SD_CS_PIN;
    slot_config.gpio_miso = SD_MISO_PIN;
    slot_config.gpio_mosi = SD_MOSI_PIN;
    slot_config.gpio_sck = SD_CLK_PIN;
    
    // Mount SD card
    ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to mount SD card: %s", esp_err_to_name(ret));
        return;
    }
    
    // Card info
    ESP_LOGI(TAG, "SD Card mounted, card info:");
    ESP_LOGI(TAG, "Name: %s", card->cid.name);
    ESP_LOGI(TAG, "Capacity: %lluMB", ((uint64_t) card->csd.capacity) * card->csd.sector_size / (1024 * 1024));
    
    // Write test file
    FILE* f = fopen("/sdcard/test.txt", "w");
    if (f == NULL) {
        ESP_LOGE(TAG, "Failed to open file for writing");
        return;
    }
    fprintf(f, "Hello SD Card from ESP32 QEMU!");
    fclose(f);
    ESP_LOGI(TAG, "Test file written to SD card");
}

static void touch_task(void *pvParameter)
{
    spi_device_handle_t *spi = (spi_device_handle_t*)pvParameter;
    ft6x36_touch_info_t touch_info;
    
    while (1) {
        if (ft6x36_read_touch(&touch_info) == ESP_OK && touch_info.touch_count > 0) {
            // Draw touch point
            for (int i = 0; i < touch_info.touch_count; i++) {
                ESP_LOGI(TAG, "Touch %d: (%d, %d)", i, touch_info.points[i].x, touch_info.points[i].y);
                ili9341_fill_circle(*spi, touch_info.points[i].x, touch_info.points[i].y, 5, ILI9341_RED);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// Funzione per testare la PSRAM se disponibile
static void test_psram(void)
{
    size_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t total_psram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    
    if (total_psram > 0) {
        ESP_LOGI(TAG, "PSRAM rilevata!");
        ESP_LOGI(TAG, "PSRAM totale: %d bytes", total_psram);
        ESP_LOGI(TAG, "PSRAM libera: %d bytes", free_psram);
        
        // Test di allocazione sulla PSRAM
        size_t test_size = 1024 * 1024; // 1MB
        ESP_LOGI(TAG, "Test allocazione %d bytes sulla PSRAM...", test_size);
        
        void* ptr = heap_caps_malloc(test_size, MALLOC_CAP_SPIRAM);
        if (ptr) {
            ESP_LOGI(TAG, "Allocazione riuscita!");
            // Scriviamo e leggiamo per verificare la funzionalità
            memset(ptr, 0xAA, test_size);
            bool test_ok = true;
            uint8_t* test_ptr = (uint8_t*)ptr;
            for (int i = 0; i < test_size; i++) {
                if (test_ptr[i] != 0xAA) {
                    test_ok = false;
                    break;
                }
            }
            ESP_LOGI(TAG, "Test memoria PSRAM: %s", test_ok ? "OK" : "FALLITO");
            heap_caps_free(ptr);
        } else {
            ESP_LOGE(TAG, "Allocazione fallita!");
        }
    } else {
        ESP_LOGW(TAG, "PSRAM non disponibile o non configurata.");
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Initializing peripherals");
    
    // Test PSRAM
    test_psram();
    
    // Init LCD
    spi_device_handle_t spi;
    init_lcd();
    
    // Init touch
    init_touch();
    
    // Init SD card
    init_sd_card();
    
    // Create touch task
    xTaskCreate(touch_task, "touch_task", 4096, &spi, 5, NULL);
    
    ESP_LOGI(TAG, "All peripherals initialized");
}
EOF
```

## 8. Compilazione del progetto

Compiliamo il progetto per l'ESP32:

```bash
cd ~/esp/esp32-lcd-touch-sd-demo
idf.py build
```

## 9. Emulazione con QEMU

Ora possiamo eseguire il nostro progetto in QEMU con il supporto completo:

### Emulazione senza PSRAM

```bash
~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -drive file=~/esp/sdcard.img,if=sd,format=raw \
  -display sdl \
  -cpu esp32 \
  -loadvm/xtensa-soft-mmu \
  -nographic \
  -no-reboot \
  -L ~/esp/qemu_esp32_lcd.cfg \
  -kernel ~/esp/esp32-lcd-touch-sd-demo/build/esp32-lcd-touch-sd-demo.elf
```

### Emulazione con PSRAM abilitata

Se hai configurato la PSRAM e vuoi assicurarti che sia abilitata, modifica il file di configurazione QEMU prima di eseguire:

```bash
# Abilita la PSRAM nel file di configurazione
sed -i '' 's/enabled = false/enabled = true/' ~/esp/qemu_esp32_lcd.cfg

# Esegui QEMU con memoria estesa per supportare la PSRAM
~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 8M \  # Aumentato a 8MB per includere la PSRAM
  -drive file=~/esp/sdcard.img,if=sd,format=raw \
  -display sdl \
  -cpu esp32 \
  -loadvm/xtensa-soft-mmu \
  -nographic \
  -no-reboot \
  -L ~/esp/qemu_esp32_lcd.cfg \
  -kernel ~/esp/esp32-lcd-touch-sd-demo/build/esp32-lcd-touch-sd-demo.elf
```

## 10. Interazione con l'emulatore

Una volta avviato l'emulatore:

1. Vedrai una finestra SDL che mostra l'output del display LCD
2. Puoi interagire con il touch screen usando il mouse
3. I file scritti sulla scheda SD saranno salvati nell'immagine `sdcard.img`

Per uscire dall'emulatore, premi `Ctrl+A` seguito da `X`.

## Risoluzione dei problemi comuni

### QEMU si chiude inaspettatamente

Verifica che il file di configurazione QEMU sia corretto e che tutte le dipendenze siano installate:

```bash
brew reinstall qemu --with-sdl2 --with-gtk+3
```

### Problemi con il display

Se il display non viene visualizzato correttamente:

```bash
# Controlla che SDL sia installato e funzionante
brew reinstall sdl2
```

### Errori di compilazione

Se riscontri errori durante la compilazione del progetto:

```bash
# Aggiorna l'ESP-IDF e tutte le dipendenze
cd ~/esp/esp-idf
git pull
git submodule update --init --recursive
./install.sh
```

### Problemi con la PSRAM

Se la PSRAM non viene riconosciuta correttamente nel codice:

1. Verifica che la PSRAM sia abilitata nel file di configurazione QEMU:
   ```bash
   grep -A 3 "\[psram\]" ~/esp/qemu_esp32_lcd.cfg
   ```

2. Assicurati che le opzioni della PSRAM siano abilitate nella configurazione del progetto:
   ```bash
   cd ~/esp/esp32-lcd-touch-sd-demo
   idf.py menuconfig
   ```
   Naviga fino a "Component config" → "ESP32-specific" → "Support for external, SPI-connected RAM" e verifica che tutte le opzioni necessarie siano abilitate.

3. Se stai usando una versione specifica dell'ESP-IDF, controlla la documentazione per quella versione per assicurarti che supporti la PSRAM:
   ```bash
   cd ~/esp/esp-idf
   git checkout master  # O un'altra versione con supporto PSRAM completo
   ./install.sh
   ```

## Note aggiuntive

- Per modificare la risoluzione del display LCD, modifica i parametri `width` e `height` nel file di configurazione QEMU
- Per cambiare le dimensioni della scheda SD, modifica il parametro `count` nel comando `dd`
- Per un'emulazione più realistica, puoi modificare la velocità della CPU con il parametro `-cpu-freq` (in Hz)
- Per l'emulazione della PSRAM, puoi modificare la dimensione modificando il parametro `size` nella sezione `[psram]` del file di configurazione QEMU
- Se desideri un'emulazione ancora più completa, puoi aggiungere altri dispositivi periferici come sensori I2C, interfacce di rete, ecc., seguendo lo stesso pattern di configurazione nel file QEMU

### Ottimizzazioni per la PSRAM

Se stai sviluppando un'applicazione che fa un uso intensivo della PSRAM, considera queste ottimizzazioni:

1. Usa `heap_caps_malloc(size, MALLOC_CAP_SPIRAM)` per allocare specificamente nella PSRAM
2. Per migliorare le prestazioni, puoi configurare quale memoria utilizzare per determinate attività nel menuconfig:
   - "Component config" → "ESP32-specific" → "Support for external, SPI-connected RAM" → "Try to allocate memories of WiFi and LWIP in SPIRAM firstly"
   - "Component config" → "ESP32-specific" → "Support for external, SPI-connected RAM" → "Allow .bss segment placed in external memory"

3. Puoi monitorare l'uso della PSRAM durante l'esecuzione:
   ```c
   ESP_LOGI(TAG, "PSRAM libera: %d KB", heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024);
   ```