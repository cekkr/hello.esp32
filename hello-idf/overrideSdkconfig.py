#!/usr/bin/env python3

import os
import re
from pathlib import Path

def modify_sdkconfig(sdkconfig_path):
    """
    Modifica o aggiunge le configurazioni di sicurezza nell'sdkconfig
    """
    # Dizionario delle configurazioni da impostare
    security_configs = {
        "CONFIG_ESP_SYSTEM_CHECK_INT_LEVEL": "5",
        "CONFIG_ESP_SYSTEM_PANIC": "1",
        "CONFIG_ESP_SYSTEM_PANIC_PRINT_REBOOT": "y",
        "CONFIG_ESP_SYSTEM_PANIC_SILENT_REBOOT": "n",
        "CONFIG_ESP_SYSTEM_PANIC_GDBSTUB": "n",
        "CONFIG_COMPILER_STACK_CHECK_MODE_STRONG": "n",
        "CONFIG_COMPILER_STACK_CHECK_MODE_NORMAL": "n",
        "CONFIG_ESP_STACK_TRACE_ENABLED": "y",
        "CONFIG_HEAP_POISONING_COMPREHENSIVE": "y",
        "CONFIG_HEAP_TRACING_STANDALONE": "y",
        "CONFIG_ESP_TASK_WDT": "y",
        "CONFIG_ESP_TASK_WDT_PANIC": "y",
        "CONFIG_ESP_TASK_WDT_TIMEOUT_S": "5",
        "CONFIG_LOG_DEFAULT_LEVEL_DEBUG": "y",
        "CONFIG_LOG_COLORS": "y",
        "CONFIG_ESP_INT_WDT": "y",
        "CONFIG_ESP_INT_WDT_TIMEOUT_MS": "300",
        "CONFIG_ESP_INT_WDT_CHECK_CPU1": "y",
        "CONFIG_HEAP_POISONING_LIGHT": "n",
        "CONFIG_HEAP_TRACING": "y",
        "CONFIG_HEAP_ABORT_WHEN_ALLOCATION_FAILS": "y",
        "CONFIG_ESP_SYSTEM_EVENT_QUEUE_SIZE": "32",
        "CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE": "2304",
        "CONFIG_ESP_MAIN_TASK_STACK_SIZE": "4096",
        "CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0": "y",
        "CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU1": "y",
        "CONFIG_COMPILER_OPTIMIZATION_LEVEL_DEBUG": "n",
        "CONFIG_COMPILER_OPTIMIZATION_LEVEL_RELEASE": "n",
        "CONFIG_COMPILER_WARN_WRITE_STRINGS": "n",
        "CONFIG_COMPILER_DISABLE_GCC8_WARNINGS": "y",
        "CONFIG_FATFS_LFN_STACK_BUFFER_SIZE":"256",
        "CONFIG_FATFS_USE_LFN":"1",
        "CONFIG_FATFS_MAX_LFN":"255",
        "CONFIG_ESP32_INSTRUCTION_CACHE_SIZE": "64",
        "CONFIG_ESP_SYSTEM_MEMPROT_FEATURE": "n",
        "CONFIG_ESP_HEAP_TASK_STACK_SIZE": "32768",
        "CONFIG_ESP_MAIN_TASK_STACK_SIZE": "8192",
        "CONFIG_ESP_SYSTEM_MEMPROT_FEATURE":"n",  # Disabilita temporaneamente per debug
        "CONFIG_HEAP_POISONING_DISABLED":"n",  # Per debug
        "CONFIG_HEAP_TRACING_STANDALONE":"y",
        "CONFIG_ESP32_ENABLE_COREDUMP_TO_FLASH":"y",
        "CONFIG_ESP32_ENABLE_COREDUMP":"y"
    }

    # Leggi il file esistente
    try:
        with open(sdkconfig_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
        print(f"File {sdkconfig_path} non trovato, verrà creato un nuovo file")

    # Tieni traccia delle configurazioni trovate
    found_configs = set()

    # Modifica le linee esistenti
    for i, line in enumerate(lines):
        for config, value in security_configs.items():
            if line.startswith(f"{config}="):
                lines[i] = f"{config}={value}\n"
                found_configs.add(config)
                break

    # Aggiungi le configurazioni mancanti
    missing_configs = set(security_configs.keys()) - found_configs
    for config in missing_configs:
        lines.append(f"{config}={security_configs[config]}\n")

    # Scrivi il file aggiornato
    with open(sdkconfig_path, 'w') as f:
        f.writelines(lines)

def main():
    # Cerca l'sdkconfig nella directory corrente o nelle directory parent
    current_dir = Path.cwd()
    sdkconfig_path = None
    
    while current_dir.parent != current_dir:
        if (current_dir / "sdkconfig").exists():
            sdkconfig_path = current_dir / "sdkconfig"
            break
        current_dir = current_dir.parent

    if sdkconfig_path is None:
        sdkconfig_path = Path.cwd() / "sdkconfig"
        print("sdkconfig non trovato, verrà creato nella directory corrente")

    print(f"Modificando {sdkconfig_path}")
    modify_sdkconfig(sdkconfig_path)
    print("Configurazioni di sicurezza applicate con successo")

if __name__ == "__main__":
    main()
    