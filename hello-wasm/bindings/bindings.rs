// Auto-generated Rust bindings for ESP32 WASM

#[link(wasm_import_module = "env")]
extern "C" {
    pub fn esp_printf(format: *const i8, args: *const i32, vararg_count: i32) -> ();

    pub fn lcd_draw_text(x: i32, y: i32, size: i32, text: *const i8) -> ();

    pub fn esp_add(a: i32, b: i32) -> i32;

    pub fn esp_read_serial() -> *mut i8;

}