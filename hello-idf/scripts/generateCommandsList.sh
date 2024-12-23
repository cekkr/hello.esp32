#!/bin/bash

source ./espShellEnv.sh

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