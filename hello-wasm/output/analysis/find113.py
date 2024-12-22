def find_113_in_wasm(wasm_file_path):
    # Legge il file WASM in modalità binaria
    with open(wasm_file_path, 'rb') as f:
        wasm_bytes = f.read()
    
    # 113 in little-endian a 32 bit
    target = (113).to_bytes(4, byteorder='little')
    
    # Cerca tutte le occorrenze
    positions = []
    offset = 0
    
    while True:
        pos = wasm_bytes.find(target, offset)
        if pos == -1:
            break
        positions.append(pos)
        offset = pos + 1
    
    # Stampa i risultati
    print(f"Numero di occorrenze di 113 (32-bit): {len(positions)}")
    for pos in positions:
        print(f"Trovato a offset: 0x{pos:08x} (decimale: {pos})")
        # Mostra alcuni byte prima e dopo per contesto
        context_start = max(0, pos - 8)
        context_end = min(len(wasm_bytes), pos + 12)
        context = wasm_bytes[context_start:context_end]
        print("Contesto (hex):", ' '.join(f'{b:02x}' for b in context))
        print()

# Uso:
find_113_in_wasm("../fibonacciPrint.wasm")