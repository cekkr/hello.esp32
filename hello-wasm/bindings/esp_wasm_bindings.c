#include "esp_wasm_bindings.h"
#include "wasm3.h"
#include "m3_env.h"

// Auto-generated WASM binding implementations

m3ApiRawFunction(esp_led_write) {
    m3ApiReturnType(void)
    m3ApiGetArg(int32_t, pin)
    m3ApiGetArg(int32_t, level)
    esp_led_write_impl(pin, level);
    m3ApiSuccess();
}

m3ApiRawFunction(esp_adc_read) {
    m3ApiReturnType(int32_t)
    m3ApiGetArg(int32_t, channel)
    m3ApiReturn(esp_adc_read_impl(channel));
}

m3ApiRawFunction(esp_get_temperature) {
    m3ApiReturnType(float)
    m3ApiReturn(esp_get_temperature_impl());
}

m3ApiRawFunction(esp_wifi_scan) {
    m3ApiReturnType(int32_t)
    m3ApiReturn(esp_wifi_scan_impl());
}

m3ApiRawFunction(esp_printf_wasm) {
    m3ApiReturnType(void)
    m3ApiGetArgCount(argCount)

    m3ApiGetArg(const char*, format)
    // Handle varargs
    int vararg_count = argCount - 1;
    int32_t* varargs = m3ApiAlloc(vararg_count * sizeof(int32_t));
    for (int i = 0; i < vararg_count; i++) {
        m3ApiGetArg(int32_t, varargs[i])
    }

    esp_printf_impl(format, varargs, vararg_count);
    m3ApiSuccess();
}

// Array of bindings
WasmBinding esp_bindings[] = {
    {"esp_led_write", esp_led_write, "v(ii)"},
    {"esp_adc_read", esp_adc_read, "i(i)"},
    {"esp_get_temperature", esp_get_temperature, "i()"},
    {"esp_wifi_scan", esp_wifi_scan, "i()"},
    {"esp_printf", esp_printf_wasm, "v(i)"},
};

size_t esp_bindings_count = sizeof(esp_bindings) / sizeof(WasmBinding);
