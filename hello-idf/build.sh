#!/bin/bash

export IDF_PATH="/Users/riccardo/Sources/Libs/esp-idf-v5.3.1"
alias python=python3

CUR_DIR=$(pwd)

cd "$IDF_PATH"
# Salva la directory corrente di IDF_PATH
IDF_PWD=$(pwd)  

. ./export.sh

# Torna alla directory di IDF_PATH (potrebbe essere stata modificata da export.sh)
cd "$IDF_PWD" 
cd "$CUR_DIR"

#mkdir -p build
#cd build
#cmake ..
#make

idf.py set-target esp32
#idf.py menuconfig
idf.py build

#idf.py -p COM3 flash    # Windows
#idf.py -p /dev/ttyUSB0 flash    # Linux
idf.py -p /dev/tty.usbserial-1140 flash -b 115200    # MacOS

#idf.py monitor