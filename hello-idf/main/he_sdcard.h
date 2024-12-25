#ifndef HELLOESP_SDCARD_H
#define HELLOESP_SDCARD_H

#include <sys/unistd.h>
#include <sys/stat.h>



void init_sd_pins();
bool init_sd_card();
void mostra_info_sd(const char* mount_point);
#endif