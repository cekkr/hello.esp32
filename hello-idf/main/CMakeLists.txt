
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

###
###

set(SDKCONFIG_DEFAULTS
    ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults
    ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.custom
)

set(CONFIG_LOG_DEFAULT_LEVEL_DEBUG 1 CACHE STRING "Set log level to DEBUG")
set(CONFIG_WASM3_DEBUG_MACROS 1 CACHE BOOL "Enable WASM3 debug macros")

if(DEBUG_BUILD)
    idf_build_set_property(COMPILE_OPTIONS "-DCONFIG_LOG_DEFAULT_LEVEL=4" APPEND)
endif()

# Nel CMakeLists.txt del componente
idf_component_set_property(wasm3 COMPILE_DEFINITIONS "CONFIG_WASM3_DEBUG_MACROS=1;CONFIG_LOG_DEFAULT_LEVEL=4" APPEND)

set(CONFIG_WASM3_STACK_CHECK 1 CACHE BOOL "Enable stack checking in WASM3")
if(CONFIG_WASM3_STACK_CHECK)
    target_compile_definitions(${COMPONENT_TARGET} PRIVATE CONFIG_WASM3_STACK_CHECK=1)
endif()