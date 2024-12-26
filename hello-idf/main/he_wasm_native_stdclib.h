#ifndef HELLOESP_NATIVE_STDCLIB_H
#define HELLOESP_NATIVE_STDCLIB_H

#include <stdint.h>
#include <stdarg.h>

#include "m3_env.h"

// Common error messages
#define ERROR_INVALID_MEMORY "Invalid memory access"
#define ERROR_NULL_POINTER "Null pointer argument"
#define ERROR_INVALID_ARGUMENT "Invalid argument"

M3Result RegisterStandardCLibFunctions(IM3Module module, m3_wasi_context_t *ctx);

#endif 
