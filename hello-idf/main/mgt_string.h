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
void init_string_buffer(StringBuffer* str_buf) {
    str_buf->position = 0;
    str_buf->max_length = MAX_STRING_LENGTH;

    str_buf->buffer = malloc(str_buf->max_length);
    str_buf->buffer[0] = '\0';
}

// Free the memory allocated for the string buffer
void free_string_buffer(StringBuffer* str_buf) {
    free(str_buf->buffer);
}

char* string_printf(const char* format, ...) { // FANCULO, usa invece: sprintf(text, "Result: %d", number);
    StringBuffer* str_buf = malloc(sizeof(StringBuffer));
    init_string_buffer(str_buf);

    va_list args;
    va_start(args, format);

    // Calculate remaining space in buffer
    size_t remaining = str_buf->max_length - str_buf->position;

    // Format string and write to buffer at current position
    int written = vsnprintf(str_buf->buffer + str_buf->position,
                            remaining,
                            format,
                            args);

    va_end(args);

    // Update position if write was successful
    if (written > 0 && written < remaining) {
        str_buf->position += written;
    }

    str_buf->buffer[str_buf->position] = '\0';

    return str_buf->buffer;
}

// Function to free the memory allocated by string_printf
void free_string(char* str) { // ???????
    StringBuffer* str_buf = (StringBuffer*)((char*)str - offsetof(StringBuffer, buffer));
    free_string_buffer(str_buf);
    free(str_buf);
}

/*
Example:
char* str = string_printf("Hello, %s! Value: %d", "world", 42);
printf("%s\n", str);
free_string(str);
*/

// Custom printf that writes to a string buffer
int stringBuffer_printf(StringBuffer* str_buf, const char* format, ...) {
    //taskENTER_CRITICAL();  // Enter critical section if needed
    
    va_list args;
    va_start(args, format);
    
    // Calculate remaining space in buffer
    size_t remaining = str_buf->max_length - str_buf->position;
    
    // Format string and write to buffer at current position
    int written = vsnprintf(str_buf->buffer + str_buf->position, 
                           remaining, 
                           format, 
                           args);
    
    va_end(args);
    
    // Update position if write was successful
    if (written > 0 && written < remaining) {
        str_buf->position += written;
    }
    
    //taskEXIT_CRITICAL();  // Exit critical section
    
    return written;
}

// Convert StringBuffer to char array (copying)
void string_buffer_to_array(const StringBuffer* str_buf, char* dest, size_t dest_size) {
    //taskENTER_CRITICAL();
    
    // Ensure we don't overflow the destination buffer
    size_t copy_size = (str_buf->position < dest_size - 1) ? 
                       str_buf->position : 
                       dest_size - 1;
    
    // Copy the string
    memcpy(dest, str_buf->buffer, copy_size);
    
    // Ensure null termination
    dest[copy_size] = '\0';
    
    //taskEXIT_CRITICAL();
}

// Get pointer to internal buffer (no copying)
const char* string_buffer_get_string(const StringBuffer* str_buf) {
    return str_buf->buffer;
}

// Get current length of the string
size_t string_buffer_length(const StringBuffer* str_buf) {
    return str_buf->position;
}

// Clear the string buffer
void string_buffer_clear(StringBuffer* str_buf) {
    //taskENTER_CRITICAL();
    str_buf->position = 0;
    str_buf->buffer[0] = '\0';
    //taskEXIT_CRITICAL();
}

// Example usage
void example_usage_string_printf(void) {
    StringBuffer str_buf;
    init_string_buffer(&str_buf);
    
    // Write to buffer
    stringBuffer_printf(&str_buf, "Hello %s! ", "World");
    stringBuffer_printf(&str_buf, "Number: %d ", 42);
    stringBuffer_printf(&str_buf, "Float: %.2f\n", 3.14);
    
    // Method 1: Get string by copying to a new array
    char output_array[MAX_STRING_LENGTH];
    string_buffer_to_array(&str_buf, output_array, MAX_STRING_LENGTH);
    
    // Method 2: Get direct pointer to the string
    const char* direct_string = string_buffer_get_string(&str_buf);
    
    // Get string length
    size_t len = string_buffer_length(&str_buf);
    
    // Clear buffer if needed
    string_buffer_clear(&str_buf);
}