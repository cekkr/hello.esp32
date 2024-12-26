// Auto-generated TypeScript bindings for ESP32 WASM

declare function strlen(str: number): number;

declare function strcpy(dest: number, src: number): number;

declare function strcmp(str1: number, str2: number): number;

declare function strcat(dest: number, src: number): number;

declare function malloc(size: number): number;

declare function free(ptr: number): void;

declare function realloc(ptr: number, size: number): number;

declare function memset(dest: number, c: number, count: number): number;

declare function memcmp(ptr1: number, ptr2: number, num: number): number;

declare function esp_printf(format: number, ...args: ...number[]): void;

declare function lcd_draw_text(x: number, y: number, size: number, text: number): void;

declare function esp_add(a: number, b: number): number;

declare function esp_read_serial(): number;
