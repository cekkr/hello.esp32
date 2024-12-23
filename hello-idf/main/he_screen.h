#pragma once

#include "lcd.h"
#include "gui.h"
#include "xpt2046.h"
#include "he_defines.h"

///
/// Touch Screen
///

#define CONFIG_XPT_MISO_GPIO   39
#define CONFIG_XPT_CS_GPIO     33
#define CONFIG_XPT_IRQ_GPIO    36
#define CONFIG_XPT_SCLK_GPIO   25
#define CONFIG_XPT_MOSI_GPIO   32

void init_tft(void);