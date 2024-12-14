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

# Reset CMAke clean
#if [ 0 ]; then
#    find . -name CMakeCache.txt -delete
#    find . -name CMakeFiles -type d -exec rm -rf {} +
#    rm -rf build/
#fi

#mkdir -p build
#cd build
#cmake ..
#make

#idf.py reconfigure
#idf.py clean
#idf.py fullclean

#rm -rf build # necessary everytime?

#idf.py set-target esp32
#idf.py menuconfig

idf.py build #-DCMAKE_C_FLAGS="-H" 2>&1 | tee build_output.txt
#idf.py build -DCMAKE_BUILD_TYPE=Release
#idf.py build -DCMAKE_BUILD_TYPE=Release -DESP_SYSTEM_INIT_DEBUG_INFO=y

#idf.py -p COM3 flash    # Windows
#idf.py -p /dev/ttyUSB0 flash    # Linux
idf.py -p /dev/tty.usbserial-120 flash -b 115200    # MacOS

#idf.py monitor