
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "." "../components/XPT2046/include" "../components/LCD/include" "../components/GUI/include" 
       # "../components/wasm3-helloesp/embedded/esp32-idf-wasi/main"
    PRIV_REQUIRES fatfs
)
