/**
 * Implementation of Standard C Library Functions for WASM3 on ESP32
 * 
 * This implementation provides WASM-compatible versions of standard C library functions,
 * carefully handling memory safety and WASM memory model requirements.
 */

#include "he_wasm_native_stdclib.h"

#include <stdint.h>
#include <stdarg.h>
#include "esp_log.h"

#include "he_defines.h"
#include "he_settings.h"
#include "he_screen.h"

#include "wasm3.h"
#include "m3_pointers.h"
#include "m3_segmented_memory.h"

// Common error messages
#define ERROR_INVALID_MEMORY "Invalid memory access"
#define ERROR_NULL_POINTER "Null pointer argument"
#define ERROR_INVALID_ARGUMENT "Invalid argument"

// Helper function to validate memory access in WASM space
static bool ValidateMemoryAccess(IM3Runtime runtime, void* mem, void* ptr, size_t size) {
    if (!runtime || !mem) return false;
    return IsValidMemoryAccess((IM3Memory)mem, (mos)ptr, size);
}

// Helper function to safely resolve and validate pointers
static void* SafeResolvePtr(IM3Runtime runtime, void* mem, void* ptr, size_t size) {
    if (!ValidateMemoryAccess(runtime, mem, ptr, size)) {
        return NULL;
    }
    return m3_ResolvePointer(mem, ptr);
}

/************************* String Functions *************************/

// strlen implementation for WASM
M3Result wasm_strlen(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    m3ApiReturnType  (uint32_t)
    m3ApiGetArg      (const char*, str)

    // Input validation
    if (!ValidateMemoryAccess(runtime, _mem, (void*)str, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    const char* real_str = m3_ResolvePointer(_mem, str);
    size_t len = 0;
    
    // Safe string length calculation with bounds checking
    while (ValidateMemoryAccess(runtime, _mem, (void*)(str + len), 1) && real_str[len] != '\0') {
        len++;
    }

    *raw_return = (uint32_t)len;
    return m3Err_none;
}

// strcpy implementation for WASM
M3Result wasm_strcpy(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    m3ApiReturnType  (char*)
    m3ApiGetArg      (char*, dest)
    m3ApiGetArg      (const char*, src)

    // Input validation
    if (!ValidateMemoryAccess(runtime, _mem, dest, 1) || 
        !ValidateMemoryAccess(runtime, _mem, (void*)src, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    char* real_dest = m3_ResolvePointer(_mem, dest);
    const char* real_src = m3_ResolvePointer(_mem, src);
    
    // Get source length for validation
    size_t src_len = 0;
    while (ValidateMemoryAccess(runtime, _mem, (void*)(src + src_len), 1) && 
           real_src[src_len] != '\0') {
        src_len++;
    }
    src_len++; // Include null terminator

    // Validate destination has enough space
    if (!ValidateMemoryAccess(runtime, _mem, dest, src_len)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    // Perform the copy
    M3Result result = m3_memcpy(_mem, real_dest, real_src, src_len);
    if (result) return result;

    *raw_return = dest;
    return m3Err_none;
}

/************************* Memory Functions *************************/

// malloc implementation for WASM
M3Result wasm_malloc(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    m3ApiReturnType  (void*)
    m3ApiGetArg      (uint32_t, size)

    // Allocate memory using WASM3's memory allocator
    void* ptr = m3_malloc(_mem, size);
    if (!ptr) {
        return m3Err_mallocFailed;
    }

    *raw_return = ptr;
    return m3Err_none;
}

// free implementation for WASM
M3Result wasm_free(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    m3ApiGetArg      (void*, ptr)

    if (ptr) {
        m3_free(_mem, ptr);
    }

    return m3Err_none;
}

// realloc implementation for WASM
M3Result wasm_realloc(IM3Runtime runtime, IM3ImportContext *ctx, uint64_t* _sp, void* _mem) {
    m3ApiReturnType  (void*)
    m3ApiGetArg      (void*, ptr)
    m3ApiGetArg      (uint32_t, size)

    void* new_ptr = m3_realloc(_mem, ptr, size);
    if (!new_ptr && size > 0) {
        return m3Err_mallocFailed;
    }

    *raw_return = new_ptr;
    return m3Err_none;
}

// Initial function table
const WasmFunctionEntry stdlibFunctionTable[] = {
    // String functions
    {
        .name = "strlen",
        .func = wasm_strlen,
        .signature = "i(*)"  // uint32_t (const char*)
    },
    {
        .name = "strcpy",
        .func = wasm_strcpy,
        .signature = "*(**)"  // char* (char*, const char*)
    },
    // Memory functions
    {
        .name = "malloc",
        .func = wasm_malloc,
        .signature = "*(i)"  // void* (size_t)
    },
    {
        .name = "free",
        .func = wasm_free,
        .signature = "v(*)"  // void (void*)
    },
    {
        .name = "realloc",
        .func = wasm_realloc,
        .signature = "*(*i)"  // void* (void*, size_t)
    }
};

/**
 * Registers the standard C library functions with the WASM runtime
 * 
 * @param runtime The WASM3 runtime instance
 * @return M3Result indicating success or failure
 */
M3Result RegisterStandardCLibFunctions(IM3Module module, m3_wasi_context_t *ctx) {
    M3Result result = RegisterWasmFunctions(module, stdlibFunctionTable, sizeof(stdlibFunctionTable)/sizeof(stdlibFunctionTable[0]), ctx);
    if (result) {
        ESP_LOGE(TAG, "Failed to register Standard C Lib functions: %s", result);
    }

    return result;
}