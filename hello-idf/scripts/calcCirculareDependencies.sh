#!/bin/bash
# Apparently not working (so the _ at the filename beginning)

source ./espShellEnv.sh

#https://claude.ai/chat/274ad940-174e-40eb-aba7-e1e3390fd1cf

idf.py --cmake-preprocess components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/extensions/m3_extensions.c > preprocessed.txt

#xtensa-esp32-elf-gcc -E -I(percorsi include) components/wasm3-helloesp/platforms/embedded/esp32-idf-wasi/wasm3/wasm3/extensions/m3_extensions.c > preprocessed.txt