#!/bin/bash

source ./espShellEnv.sh

#COREDUMP_OFFSET=$(parttool.py --port $ESP_DEV get_partition_info --partition-type data --partition-subtype coredump | grep "0x" | tail -n1 | awk '{print $1}')

# Per verificare che abbiamo l'offset corretto
#echo $COREDUMP_OFFSET

#esptool.py -p $ESP_DEV read_flash $COREDUMP_OFFSET 0x10000 coredump.bin

#parttool.py --port $ESP_DEV get_partition_info --partition-type data --partition-subtype coredump

espcoredump.py -p $ESP_DEV --baud 115200 info_corefile build/hello-idf.elf

#esptool.py -p $ESP_DEV read_flash 0x110000 0x10000 coredump.bin
