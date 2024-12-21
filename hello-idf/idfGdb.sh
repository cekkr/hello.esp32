#!/bin/bash

source ./espShellEnv.sh

#idf.py gdb

export OPENOCD_COMMANDS="-f interface/wch-link.cfg -f target/esp32.cfg"

idf.py openocd
#which openocd

#openocd -c "adapter serial $ESP_DEV" -c "adapter driver usbprog" -c "transport select uart" -f target/esp32.cfg 

#-c "transport select uart" -c "adapter speed 20000" 

#1: ftdi
#2: usb_blaster
#3: esp_usb_jtag
#4: ft232r
#5: usbprog
#6: jlink
#7: vsllink
#8: rlink
#9: ulink
#10: angie
#11: arm-jtag-ew
#12: buspirate
#13: remote_bitbang
#14: hla
#15: osbdm
#16: opendous
#17: cmsis-dap
#18: kitprog
#19: xds110
#20: st-link
#21: jtag_esp_remote