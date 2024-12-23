#ifndef HELLOESP_MGT_STRING_H
#define HELLOESP_MGT_STRING_H

#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

// Buffer size for the output string
#define MAX_STRING_LENGTH 256

// Structure to hold the buffer and its properties
typedef struct {
    char* buffer;
    size_t position;
    size_t max_length;
} StringBuffer;

// Initialize the string buffer
void init_string_buffer(StringBuffer* str_buf);

// Free the memory allocated for the string buffer
void free_string_buffer(StringBuffer* str_buf);

char* string_printf(const char* format, ...);

// Function to free the memory allocated by string_printf
void free_string(char* str);

/*
Example:
char* str = string_printf("Hello, %s! Value: %d", "world", 42);
printf("%s\n", str);
free_string(str);
*/

// Custom printf that writes to a string buffer
int stringBuffer_printf(StringBuffer* str_buf, const char* format, ...);

// Convert StringBuffer to char array (copying)
void string_buffer_to_array(const StringBuffer* str_buf, char* dest, size_t dest_size);

// Get pointer to internal buffer (no copying)
const char* string_buffer_get_string(const StringBuffer* str_buf);

// Get current length of the string
size_t string_buffer_length(const StringBuffer* str_buf);

// Clear the string buffer
void string_buffer_clear(StringBuffer* str_buf);

#endif  // HELLOESP_MGT_STRING_H