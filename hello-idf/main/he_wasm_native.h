#ifndef HELLOESP_NATIVE_H
#define HELLOESP_NATIVE_H

#include "he_defines.h"

#include <stdint.h>
#include <stdarg.h>

#include "m3_env.h"

///
///
///

M3Result wasm_esp_printf(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem);

M3Result wasm_lcd_draw_text(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem);

M3Result wasm_esp_add(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem);

M3Result wasm_esp_read_serial(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem);

///
///
///

M3Result registerNativeWASMFunctions(IM3Module module, m3_wasi_context_t *ctx);

#endif 
