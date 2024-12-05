#!/bin/bash
# Apparently not working

#export IDF_PATH="/Users/riccardo/Sources/Libs/esp-idf-v5.3.1"
#alias python=python3

CUR_DIR=$(pwd)

cd "$IDF_PATH"
# Salva la directory corrente di IDF_PATH
IDF_PWD=$(pwd)  

. ./export.sh

# Torna alla directory di IDF_PATH (potrebbe essere stata modificata da export.sh)
cd "$IDF_PWD" 
cd "$CUR_DIR"

#https://claude.ai/chat/274ad940-174e-40eb-aba7-e1e3390fd1cf

idf.py --cmake-preprocess components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/extensions/m3_extensions.c > preprocessed.txt

#xtensa-esp32-elf-gcc -E -I(percorsi include) components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/extensions/m3_extensions.c > preprocessed.txt