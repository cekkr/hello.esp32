#!/bin/bash

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

if [ 0 ]; then
    find . -name CMakeCache.txt -delete
    find . -name CMakeFiles -type d -exec rm -rf {} +
    rm -rf build/
fi

#cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON .
#idf.py reconfigure -- -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

#idf.py set-target esp32
#idf.py fullclean
#idf.py compile-commands

idf.py -G Ninja set-target esp32
idf.py -G Ninja fullclean
#idf.py -G Ninja compile-commands
idf.py reconfigure -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

rm -rf build-cmds
mv build build-cmds