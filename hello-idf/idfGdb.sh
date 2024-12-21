#!/bin/bash

source ./espShellEnv.sh

#idf.py gdb

#openocd -f interface/ftdi/esp32_devkitj_v1.cfg -f target/esp32.cfg -c "adapter_khz 1000" -c "adapter serial $ESP_DEV"

idf.py openocd
