#ifndef ESP32_WASM_BINDINGS_H
#define ESP32_WASM_BINDINGS_H

#include <stdint.h>
#include <stdbool.h>

// or #ifdef __MEMORY64__
#ifdef __EMSCRIPTEN_WASM64__
typedef uint64_t _size_t;
#else
typedef uint32_t _size_t;
#endif

///
/// Standard C Library
///

// String functions
/*extern _size_t strlen(const char* str) 
    __attribute__((import_module("env"), import_name("strlen")));

extern char* strcpy(char* dest, const char* src) 
    __attribute__((import_module("env"), import_name("strcpy")));

extern int strcmp(const char* str1, const char* str2) 
    __attribute__((import_module("env"), import_name("strcmp")));

extern char* strcat(char* dest, const char* src) 
    __attribute__((import_module("env"), import_name("strcat")));

// Memory functions
extern void* malloc(_size_t size) 
    __attribute__((import_module("env"), import_name("malloc")));

extern void free(void* ptr) 
    __attribute__((import_module("env"), import_name("free")));

extern void* realloc(void* ptr, _size_t size) 
    __attribute__((import_module("env"), import_name("realloc")));

extern void* memset(void* dest, int c, _size_t count) 
    __attribute__((import_module("env"), import_name("memset")));

extern int memcmp(const void* ptr1, const void* ptr2, _size_t num) 
    __attribute__((import_module("env"), import_name("memcmp")));*/

///
/// Hello ESP functions
///

extern void esp_printf(const char* format, ...)  __attribute__((import_module("env"), import_name("esp_printf")));

extern void lcd_draw_text(int x, int y, int size, const char* text)  __attribute__((import_module("env"), import_name("lcd_draw_text")));

extern int esp_add(int a, int b)  __attribute__((import_module("env"), import_name("esp_add")));

extern char* esp_read_serial()  __attribute__((import_module("env"), import_name("esp_read_serial")));

#endif // ESP32_WASM_BINDINGS_H
