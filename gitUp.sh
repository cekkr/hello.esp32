#!/bin/bash

# Funzione per gestire gli errori
handle_error() {
    echo "Errore: $1"
    exit 1
}

# Funzione per fare commit in una directory
do_git_commit() {
    local dir=$1
    echo "Processando directory: $dir"
    
    # Verifica se la directory esiste
    if [ ! -d "$dir" ]; then
        handle_error "La directory $dir non esiste"
    fi
    
    # Entra nella directory
    cd "$dir" || handle_error "Impossibile accedere alla directory $dir"
    
    # Verifica se è una repository git
    if [ ! -d ".git" ]; then
        handle_error "La directory $dir non è una repository git"
    fi
    
    # Ottieni la data corrente per il messaggio di commit
    current_date=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Aggiungi tutti i file modificati
    git add . || handle_error "Errore durante git add in $dir"
    
    # Verifica se ci sono modifiche da committare
    if git diff --cached --quiet; then
        echo "Nessuna modifica da committare in $dir"
        return 0
    fi
    
    # Esegui il commit
    git commit -m "Auto commit: $current_date" || handle_error "Errore durante il commit in $dir"
    
    echo "Commit completato con successo in $dir"
}

# Directory corrente
current_dir=$(pwd)

# Directory helloesp.terminal
helloesp_dir="../helloesp.terminal"

# Esegui commit nella directory corrente
echo "Iniziando commit nella directory corrente..."
do_git_commit "$current_dir"

# Esegui commit nella directory helloesp.terminal
echo "Iniziando commit nella directory helloesp.terminal..."
do_git_commit "$helloesp_dir"

echo "Operazione completata con successo!"