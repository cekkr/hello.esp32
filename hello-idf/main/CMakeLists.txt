#idf_component_register(SRCS "main.c" INCLUDE_DIRS "." "../components/ili9340" REQUIRES "ili9340" nvs_flash spiffs PRIV_REQUIRES fatfs)

idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "." "../components/XPT2046/include" "../components/LCD/include" "../components/GUI/include"
    PRIV_REQUIRES fatfs
)
