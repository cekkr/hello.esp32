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


idf.py -v -DIDF_COMPILE_COMMANDS=1 -DCMAKE_VERBOSE_MAKEFILE=ON build 2>&1 | tee build_output.txt
#cd build
#make VERBOSE=1

#idf.py compiledb