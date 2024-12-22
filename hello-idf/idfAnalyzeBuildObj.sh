#!/bin/bash

source ./espShellEnv.sh

# SH args https://claude.ai/chat/647a1c48-35b7-48b6-b09e-1355dd9ca96f

export FILE="build/esp-idf/wasm3/CMakeFiles/__idf_wasm3.dir/wasm3/m3_compile.c.obj"

#clear

# Per vedere la mappatura dettagliata delle sezioni
#xtensa-esp32-elf-objdump -h $FILE

# Per vedere le funzioni e il loro posizionamento
#xtensa-esp32-elf-nm -S $FILE | sort -n

# Per vedere le funzioni in iram
xtensa-esp32-elf-objdump -d $FILE | grep -C 5 ".iram"

#grep "m3_object" build/hello-idf.map

#python3 $IDF_PATH/tools/idf_size_yaml.py --dump-toolchain-paths build/hello-idf.map > size_toolchain.yml