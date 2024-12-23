#!/bin/bash

source ./espShellEnv.sh

#idf.py reconfigure
#idf.py clean
#idf.py fullclean

#rm -rf build # necessary everytime?

#idf.py set-target esp32
#idf.py menuconfig
#idf.py build #-DCMAKE_C_FLAGS="-H" 2>&1 | tee build_output.txt

idf.py size-files

#xtensa-esp32-elf-nm -S --size-sort build/nome_progetto.elf | grep -i iram