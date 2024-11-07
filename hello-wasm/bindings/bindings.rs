// Auto-generated Rust bindings for ESP32 WASM

#[link(wasm_import_module = "env")]
extern "C" {
    // Controls an LED connected to a GPIO pin
    pub fn esp_led_write(pin: i32, level: i32) -> ();

    // Reads an ADC channel
    pub fn esp_adc_read(channel: i32) -> i32;

    // Reads the internal temperature sensor
    pub fn esp_get_temperature() -> f32;

    // Performs a WiFi scan and returns number of networks found
    pub fn esp_wifi_scan() -> i32;

}