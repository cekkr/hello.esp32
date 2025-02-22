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

#include "wasm3.h"
#include "m3_segmented_memory.h"

/************************* String Functions *************************/

// strlen implementation for WASM
M3Result wasm_strlen(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (uint32_t)
    m3ApiGetArg      (mos, str)

    // Input validation
    if (!IsValidMemoryAccess( _mem, str, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    const char* real_str = (const char*)m3_ResolvePointer(_mem, (mos)str);
    size_t len = 0;
    
    // Safe string length calculation with bounds checking
    while (IsValidMemoryAccess( _mem, (str + len), 1) && real_str[len] != '\0') {
        len++;
    }

    *raw_return = (uint32_t)len;
    return m3Err_none;
}

// strcpy implementation for WASM
M3Result wasm_strcpy(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (mos)
    m3ApiGetArg      (mos, dest)
    m3ApiGetArg      (mos, src)

    // Input validation
    if (!IsValidMemoryAccess( _mem, dest, 1) || 
        !IsValidMemoryAccess( _mem, src, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    char* real_dest = (char*)m3_ResolvePointer(_mem, (mos)dest);
    const char* real_src = (const char*)m3_ResolvePointer(_mem, (mos)src);
    
    // Get source length for validation
    size_t src_len = 0;
    while (IsValidMemoryAccess( _mem, (src + src_len), 1) && 
           real_src[src_len] != '\0') {
        src_len++;
    }
    src_len++; // Include null terminator

    // Validate destination has enough space
    if (!IsValidMemoryAccess( _mem, dest, src_len)) {
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
M3Result wasm_malloc(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
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
M3Result wasm_free(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiGetArg      (void*, ptr)

    if (ptr) {
        m3_free(_mem, ptr);
    }

    return m3Err_none;
}

// realloc implementation for WASM
M3Result wasm_realloc(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
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
// memcmp implementation for WASM
M3Result wasm_memcmp(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (int32_t)
    m3ApiGetArg      (mos, ptr1)
    m3ApiGetArg      (mos, ptr2)
    m3ApiGetArg      (uint32_t, num)

    if (!IsValidMemoryAccess( _mem, ptr1, num) || 
        !IsValidMemoryAccess( _mem, ptr2, num)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    const void* real_ptr1 = (const void*) m3_ResolvePointer(_mem, ptr1);
    const void* real_ptr2 = (const void*) m3_ResolvePointer(_mem, ptr2);

    *raw_return = memcmp(real_ptr1, real_ptr2, num);
    return m3Err_none;
}

// strcmp implementation for WASM
M3Result wasm_strcmp(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (int32_t)
    m3ApiGetArg      (mos, str1)
    m3ApiGetArg      (mos, str2)

    if (!IsValidMemoryAccess( _mem, str1, 1) || 
        !IsValidMemoryAccess( _mem, str2, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    const char* real_str1 = (const char*) m3_ResolvePointer(_mem, str1);
    const char* real_str2 = (const char*) m3_ResolvePointer(_mem, str2);

    // We need to validate the entire strings
    size_t i = 0;
    while (IsValidMemoryAccess( _mem, (str1 + i), 1) && 
           IsValidMemoryAccess( _mem, (str2 + i), 1)) {
        if (real_str1[i] != real_str2[i] || real_str1[i] == '\0') {
            break;
        }
        i++;
    }

    *raw_return = (real_str1[i] - real_str2[i]);
    return m3Err_none;
}

// memset implementation for WASM
M3Result wasm_memset(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (mos)
    m3ApiGetArg      (mos, dest)
    m3ApiGetArg      (int32_t, c)
    m3ApiGetArg      (uint32_t, count)

    if (!IsValidMemoryAccess( _mem, dest, count)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    void* real_dest = (void*)m3_ResolvePointer(_mem, dest);
    M3Result result = m3_memset(_mem, real_dest, c, count);
    if (result) return result;

    *raw_return = dest;
    return m3Err_none;
}

// strcat implementation for WASM
M3Result wasm_strcat(IM3Runtime runtime, IM3ImportContext *ctx, mos _sp, void* _mem) {
    m3ApiReturnType  (mos)
    m3ApiGetArg      (mos, dest)
    m3ApiGetArg      (mos, src)

    // First validate basic pointers
    if (!IsValidMemoryAccess( _mem, dest, 1) || 
        !IsValidMemoryAccess( _mem, src, 1)) {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    char* real_dest = (char*) m3_ResolvePointer(_mem, dest);
    const char* real_src = (const char*) m3_ResolvePointer(_mem, src);
    
    // Find end of dest string
    size_t dest_len = 0;
    while (IsValidMemoryAccess( _mem, dest + (mos)dest_len, 1) && 
           real_dest[dest_len] != '\0') {
        dest_len++;
    }

    // Copy src to end of dest
    size_t i = 0;
    while (IsValidMemoryAccess( _mem, (src + i), 1) && 
           IsValidMemoryAccess( _mem, dest + dest_len + i, 1) && 
           real_src[i] != '\0') {
        real_dest[dest_len + i] = real_src[i];
        i++;
    }

    // Add null terminator if we have space
    if (IsValidMemoryAccess( _mem, dest + dest_len + i, 1)) {
        real_dest[dest_len + i] = '\0';
    } else {
        return m3Err_trapOutOfBoundsMemoryAccess;
    }

    *raw_return = dest;
    return m3Err_none;
}

const WasmFunctionEntry stdlibFunctionTable[] = {
    // String functions
    {
        .name = "strlen",
        .func = wasm_strlen,
        .signature = "i(p)"  // uint32_t (const char*)
    },
    {
        .name = "strcpy",
        .func = wasm_strcpy,
        .signature = "p(pp)"  // char* (char*, const char*)
    },
    // Memory functions
    {
        .name = "malloc",
        .func = wasm_malloc,
        .signature = "p(p)"  // void* (size_t)
    },
    {
        .name = "free",
        .func = wasm_free,
        .signature = "v(p)"  // void (void*)
    },
    {
        .name = "realloc",
        .func = wasm_realloc,
        .signature = "p(pp)"  // void* (void*, size_t)
    },
    {
        .name = "memcmp",
        .func = wasm_memcmp,
        .signature = "i(ppp)"  // int (const void*, const void*, size_t)
    },
    {
        .name = "strcmp",
        .func = wasm_strcmp,
        .signature = "i(pp)"  // int (const char*, const char*)
    },
    {
        .name = "memset",
        .func = wasm_memset,
        .signature = "p(pii)"  // void* (void*, int, size_t)
    },
    {
        .name = "strcat",
        .func = wasm_strcat,
        .signature = "p(pp)"  // char* (char*, const char*)
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