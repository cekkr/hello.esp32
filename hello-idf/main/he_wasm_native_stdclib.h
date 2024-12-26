#ifndef HELLOESP_NATIVE_STDCLIB_H
#define HELLOESP_NATIVE_STDCLIB_H

#include <stdint.h>
#include <stdarg.h>

#include "m3_env.h"


M3Result RegisterStandardCLibFunctions(IM3Module module, m3_wasi_context_t *ctx);

#endif 
