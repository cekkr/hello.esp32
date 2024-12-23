#!/bin/bash

source ./espShellEnv.sh

espcoredump.py info_corefile --core coredump.bin --core-format raw build/hello-idf.elf