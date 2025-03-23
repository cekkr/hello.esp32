#include <stdio.h>
#include "../bindings/esp_wasm.h"

// Funzione principale
int start() {
    int numeri[10000];
    
    // Riempimento dell'array con numeri
    for (int i = 0; i < 10000; i++) {
        numeri[i] = i;  // Assegna il valore dell'indice
        
        // Stampa l'array ogni 100 numeri
        if ((i + 1) % 100 == 0) {
            esp_printf("Dopo %d elementi:\n", i + 1);
            // Stampa tutti i numeri fino ad ora
            for (int j = 0; j <= i; j++) {
                esp_printf("%d ", numeri[j]);
            }
            esp_printf("\n\n");
        }
    }
    
    return 0;
}