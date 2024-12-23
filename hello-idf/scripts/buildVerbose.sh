#!/bin/bash

source ./espShellEnv.sh

idf.py fullclean

idf.py -v -DIDF_COMPILE_COMMANDS=1 -DCMAKE_VERBOSE_MAKEFILE=ON build 2>&1 | tee build_output.txt
#cd build
#make VERBOSE=1

#idf.py compiledb