
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "." "../components/XPT2046/include" "../components/LCD/include" "../components/GUI/include" 
        #"../components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/main/wasm3"
    REQUIRES 
        esp_timer 
        esp_system 
        esp_event
        wasm3-helloesp
        esp_hw_support    # supporto hardware
        vfs               # per il filesystem virtuale
        fatfs            # per il filesystem FAT
        sdmmc           # per il supporto SD card
        freertos        # per il supporto ai thread
        mbedtls
        driver     
        wasm3  
        espcoredump        
)

target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-format -Wno-error=maybe-uninitialized)
