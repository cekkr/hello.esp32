file(GLOB HELLO_SRCS "he_serial.c" "he_io.c" "he_wasm_native.c" "he_wasm.c" "./*.c")
file(GLOB_RECURSE WASM_SRCS "wasm30/source/*.c")

idf_component_register(
    SRCS ${WASM_SRCS} ${HELLO_SRCS}
    INCLUDE_DIRS "." "../components/XPT2046/include" "../components/LCD/include" "../components/GUI/include"  "wasm30/source" 
    REQUIRES 
        esp_timer 
        esp_system 
        esp_event        
        esp_hw_support    # supporto hardware
        vfs               # per il filesystem virtuale
        fatfs            # per il filesystem FAT
        sdmmc           # per il supporto SD card
        freertos        # per il supporto ai thread
        mbedtls
        driver     
        #wasm3 #wasm3-helloesp
        espcoredump    
        spi_flash    
        esp_psram
        esp_mm
        LCD
        json
)


target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-error -O3 -DESP32 -Dd_m3MaxFunctionStackHeight=256)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter -Wno-missing-field-initializers)

target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-error=return-type -Wno-error=unused-but-set-parameter 
                        -Wno-error=unused-value -Wno-error=maybe-uninitialized -Wno-error=uninitialized -Wno-error=format
                        -Wno-error=multistatement-macros -Wno-error=implicit-int -Wno-error=implicit-function-declaration
                        -Wno-error=implicit-function-declaration -Wno-error=implicit-function-declaration -Wno-error=format-overflow=
                        -Wno-error=array-bounds= -Wno-error=format-truncation= -Wno-error=misleading-indentation
                    )

# Avoid IRAM
#target_compile_options(${COMPONENT_LIB} PRIVATE -fno-jump-tables -fno-tree-switch-conversion)

# Disable macro expansion notes during compilation
#target_compile_options(${COMPONENT_LIB} PRIVATE -ftrack-macro-expansion=0)