#!/bin/bash

compile_wasm() {
    local script_name=$1
    
    # Verify if script name was provided
    if [ -z "$script_name" ]; then
        echo "Error: Please provide the script name to compile"
        echo "Usage: compile_wasm script_name"
        return 1
    fi
    
    # Verify if source file exists
    if [ ! -f "samples/${script_name}.c" ]; then
        echo "Error: File samples/${script_name}.c does not exist"
        return 1
    fi
    
    # Create output directory if it doesn't exist
    mkdir -p output
    
    # Set default memory settings
    local memory_size="65536"
    local stack_size="16384"
    
    # Configure specific parameters for different scripts
    case $script_name in
        "justLoop")
            stack_size="4096"
            ;;
    esac
    
    echo "Compiling ${script_name}..."
    
    emcc "samples/${script_name}.c" -o "output/${script_name}.wasm" \
        -s WASM=1 \
        -s STANDALONE_WASM=0 \
        -s IMPORTED_MEMORY=1 \
        -s STACK_SIZE=${stack_size} \
        -s ALLOW_MEMORY_GROWTH=1 \
        -s EXPORTED_FUNCTIONS='["_start"]' \
        -s MEMORY64=1 \
        --no-entry \
        -O1 \
        -fno-inline 
        
    if [ $? -eq 0 ]; then
        echo "Compilation completed successfully"
    else
        echo "Error during compilation"
    fi
}

# Find all .c files in samples directory and compile them
for file in samples/*.c; do
    if [ -f "$file" ]; then
        # Extract filename without path and extension
        filename=$(basename "$file" .c)
        echo "Found file: $filename"
        compile_wasm "$filename"
    fi
done