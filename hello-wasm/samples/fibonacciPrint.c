// fibonacci.c
#include <stdint.h>

// Dichiarazione della funzione esterna
extern void esp_printf(const char* format, ...);

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
void print_fibonacci(uint32_t n) {
    esp_printf("Fibonacci series up to %d:\n", n);
    
    for(uint32_t i = 0; i <= n; i++) {
        uint32_t result = fib(i);
        esp_printf("F(%d) = %d\n", i, result);
    }
}

// Punto di ingresso del modulo WASM
void _start() {
    print_fibonacci(10); // Stampa i primi 10 numeri della serie
}