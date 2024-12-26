#!/bin/bash

source ./espShellEnv.sh

xtensa-esp32-elf-nm --size-sort -S build/hello-idf.elf

#Puoi usare `size` per vedere l'occupazione di memoria generale:
# xtensa-esp32-elf-size -A build/your_project.elf
#Per un'analisi dettagliata delle sezioni:
# xtensa-esp32-elf-objdump -h build/your_project.elf
#Per vedere i simboli ordinati per dimensione:
# xtensa-esp32-elf-nm --size-sort -S build/your_project.elf
#Quest'ultimo comando ti mostrerà le variabili globali e gli array più grandi.
