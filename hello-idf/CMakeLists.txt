# The following lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.5)

#set(EXTRA_COMPONENT_DIRS components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

##
##

#idf_build_set_property(LINK_OPTIONS "-Wl,--wrap=esp_panic_handler" APPEND)
#idf_build_set_property(COMPILE_DEFINITIONS "-DCONFIG_WASM3_DEBUG_MACROS=1" APPEND)

###
###

project(hello-idf)

# Create a SPIFFS image from the contents of the 'font' directory
# that fits the partition named 'storage'. FLASH_IN_PROJECT indicates that
# the generated image should be flashed when the entire project is flashed to
# the target with 'idf.py -p PORT flash
#spiffs_create_partition_image(storage0 font FLASH_IN_PROJECT)
#spiffs_create_partition_image(storage1 icons FLASH_IN_PROJECT)
#spiffs_create_partition_image(storage2 images FLASH_IN_PROJECT)

idf_build_set_property(COMPILE_OPTIONS "-Wno-error" APPEND)
set_property(DIRECTORY PROPERTY CLEAN_NO_CUSTOM 1)