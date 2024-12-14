// fibonacciPrint.c
#include <stdint.h>
#include <emscripten.h>

#include "../bindings/bindings.c"

// Funzione che calcola l'n-esimo numero di Fibonacci
uint32_t fib(uint32_t n) {
    // Versione semplificata senza debug interno
    if (n <= 1) {
        return n;
    }
    
    uint32_t prev = 0, curr = 1;
    
    for(uint32_t i = 2; i <= n; i++) {
        uint32_t next = prev + curr;
        prev = curr;
        curr = next;
    }
    
    return curr;
}

// Funzione principale che stampa la serie con debug minimo
EMSCRIPTEN_KEEPALIVE
void print_fibonacci(uint32_t n) {
    const char* fmt1 = "Fibonacci series up to %d:\n";
    const char* fmt2 = "F(%d) = %d\n";
    
    esp_printf(fmt1, n);
    
    for(uint32_t i = 0; i <= n; i++) {
        // Solo un debug print prima del calcolo
        esp_printf("Calling fib with n=%d\n", i);
        
        uint32_t result = fib(i);
        
        // E uno dopo, per vedere il risultato
        esp_printf("Got result=%d\n", result);
        
        esp_printf(fmt2, i, result);
    }
}

// Punto di ingresso
EMSCRIPTEN_KEEPALIVE
void start() {
    print_fibonacci(10);
    //return 0;
}