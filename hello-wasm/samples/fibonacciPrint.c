// fibonacciPrint.c
#include <stdint.h>
#include <emscripten.h>

// Dichiarazione della funzione esterna
void esp_printf(const char* format, ...) __attribute__((import_module("env"), import_name("esp_printf")));

// Funzione che calcola l'n-esimo numero di Fibonacci
uint32_t fib(uint32_t n) {
    if (n <= 1) return n;
    uint32_t prev = 0, curr = 1;
    
    for(uint32_t i = 2; i <= n; i++) {
        uint32_t next = prev + curr;
        prev = curr;
        curr = next;
    }
    
    return curr;
}

// Funzione principale che stampa la serie
EMSCRIPTEN_KEEPALIVE
void print_fibonacci(uint32_t n) {
    esp_printf("Fibonacci series up to %d:\n", n);
    
    for(uint32_t i = 0; i <= n; i++) {
        uint32_t result = fib(i);
        esp_printf("F(%d) = %d\n", i, result);
    }
}

// Punto di ingresso
EMSCRIPTEN_KEEPALIVE
int main() {
    print_fibonacci(10);
    return 0;
}