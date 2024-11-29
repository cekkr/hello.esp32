#ifndef NATIVE_API_H
#define NATIVE_API_H

// Funzioni GPIO
extern void gpio_set(int pin, int level);
extern int gpio_get(int pin);

// Funzioni Timer/Delay
extern void delay_ms(int ms);

// Funzioni ADC
extern int adc_read(int channel);

// Funzioni UART
extern void uart_write(int uart_num, char* data, int len);
extern int uart_read(int uart_num, char* buffer, int max_len);

// Funzioni I2C
extern void i2c_write(int addr, char* data, int len);
extern void i2c_read(int addr, char* buffer, int len);

#endif