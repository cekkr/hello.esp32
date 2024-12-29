#!/bin/bash

source ./espShellEnv.sh

#export WORKON=build/esp-idf/wasm3/CMakeFiles/__idf_wasm3.dir/wasm3/m3_info.c.obj
export WORKON=build/esp-idf/main/CMakeFiles/__idf_main.dir/wasm3/source/m3_info.c.obj

#xtensa-esp32-elf-size $WORKON
#xtensa-esp32-elf-objdump -h $WORKON
xtensa-esp32-elf-nm -S --size-sort -l $WORKON | grep " [bBdD] "
