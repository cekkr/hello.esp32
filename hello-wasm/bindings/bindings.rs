// Auto-generated Rust bindings for ESP32 WASM

#[link(wasm_import_module = "env")]
extern "C" {
    // Auto-generated ESP32 WASM bindings
Printf-like function for ESP32
    pub fn esp_printf(format: &str, args: *const i32, vararg_count: i32) -> ();

}