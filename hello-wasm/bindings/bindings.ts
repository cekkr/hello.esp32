// Auto-generated TypeScript bindings for ESP32 WASM

// Controls an LED connected to a GPIO pin
declare function esp_led_write(pin: number, level: number): void;

// Reads an ADC channel
declare function esp_adc_read(channel: number): number;

// Reads the internal temperature sensor
declare function esp_get_temperature(): number;

// Performs a WiFi scan and returns number of networks found
declare function esp_wifi_scan(): number;
