// Auto-generated Rust bindings for ESP32 WASM

#[link(wasm_import_module = "env")]
extern "C" {
    pub fn strlen(str: *const i8) -> i32;

    pub fn strcpy(dest: *mut i8, src: *const i8) -> *mut i8;

    pub fn strcmp(str1: *const i8, str2: *const i8) -> i32;

    pub fn strcat(dest: *mut i8, src: *const i8) -> *mut i8;

    pub fn malloc(size: i32) -> *mut i32;

    pub fn free(ptr: *mut i8) -> ();

    pub fn realloc(ptr: *mut i8, size: i32) -> *mut i32;

    pub fn memset(dest: *mut i8, c: i32, count: i32) -> *mut i32;

    pub fn memcmp(ptr1: *const i8, ptr2: *const i8, num: i32) -> i32;

    pub fn esp_printf(format: *const i8, args: *const i32, vararg_count: i32) -> ();

    pub fn lcd_draw_text(x: i32, y: i32, size: i32, text: *const i8) -> ();

    pub fn esp_add(a: i32, b: i32) -> i32;

    pub fn esp_read_serial() -> *mut i8;

}