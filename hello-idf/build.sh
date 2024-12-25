#!/bin/bash

source ./espShellEnv.sh

#idf.py reconfigure
#idf.py clean
#idf.py fullclean

#rm -rf build # necessary everytime?

#idf.py set-target esp32
#idf.py menuconfig

export MAKEFLAGS="-j8"
export NINJA_JOBS=8

idf.py build -DCMAKE_EXPORT_COMPILE_COMMANDS=1 #-DCMAKE_C_FLAGS="-H" 2>&1 | tee build_output.txt
#idf.py build -DCMAKE_BUILD_TYPE=Release
#idf.py build -DCMAKE_BUILD_TYPE=Release -DESP_SYSTEM_INIT_DEBUG_INFO=y

#idf.py -p COM3 flash    # Windows
#idf.py -p /dev/ttyUSB0 flash    # Linux
idf.py -p $ESP_DEV flash -b 115200    # MacOS

#idf.py monitor