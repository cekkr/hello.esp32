#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <emscripten.h>

#include "../bindings/esp_wasm.h"

#define TOTAL_INTEGERS 1000000
#define PRINT_INTERVAL 1024

// Funzione per stampare gli interi generati fino ad ora
void print_integers(int* array, int count) {
    printf("=== Stampando %d interi ===\n", count);
    for (int i = 0; i < count; i++) {
        printf("Posizione: %d, Valore: %d\n", i, array[i]);
    }
    printf("=== Fine stampa ===\n\n");
}

// Funzione principale per la generazione di interi
int start() {
    // Inizializzazione del generatore di numeri casuali
    srand(time(NULL));
    
    // Allocazione dell'array per memorizzare gli interi
    int* integers = (int*)malloc(TOTAL_INTEGERS * sizeof(int));
    if (integers == NULL) {
        printf("Errore di allocazione memoria\n");
        return 1;
    }
    
    // Generazione di interi casuali
    printf("Inizio generazione di %d interi...\n", TOTAL_INTEGERS);
    
    for (int i = 0; i < TOTAL_INTEGERS; i++) {
        // Generazione di un intero casuale
        integers[i] = rand();
        
        // Stampa ogni PRINT_INTERVAL interi
        if ((i + 1) % PRINT_INTERVAL == 0 || i == TOTAL_INTEGERS - 1) {
            print_integers(integers, i + 1);
            
            // Per Emscripten, aggiungiamo un'opportunità di aggiornare l'UI
            emscripten_sleep(0);
        }
    }
    
    printf("Generazione completata!\n");
    
    // Liberazione della memoria
    free(integers);
    
    return 0;
}