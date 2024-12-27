#!/bin/bash

source ./espShellEnv.sh

#idf.py reconfigure
#idf.py clean
#idf.py fullclean

#rm -rf build # necessary everytime?

#idf.py set-target esp32
#idf.py menuconfig
#idf.py build #-DCMAKE_C_FLAGS="-H" 2>&1 | tee build_output.txt

#idf.py build
idf.py size-files

#xtensa-esp32-elf-nm -S --size-sort build/hello-idf.elf | grep -i iram
#xtensa-esp32-elf-nm -S -l build/hello-idf.elf | sort -n

#xtensa-esp32-elf-objdump -x -d build/esp-idf/main/CMakeFiles/__idf_main.dir/wasm3/source/m3_compile.c.obj > memory_analysis.txt