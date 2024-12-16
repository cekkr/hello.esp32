#!/bin/bash

source ./espShellEnv.sh

espcoredump.py -p $ESP_DEV --baud 115200 info_corefile build/hello-idf.elf