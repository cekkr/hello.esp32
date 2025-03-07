#!/bin/bash

#export IDF_PATH="/Users/riccardo/Sources/Libs/esp-idf-v5.3.1"
#alias python=python3

#python3 overrideSdkconfig.py

clear

CUR_DIR=$(pwd)

cd "$IDF_PATH"
# Salva la directory corrente di IDF_PATH
IDF_PWD=$(pwd)  

. ./export.sh

# Torna alla directory di IDF_PATH (potrebbe essere stata modificata da export.sh)
cd "$IDF_PWD" 
cd "$CUR_DIR"

###
### Find serial port
###

#!/bin/bash

find_serial_port() {
    case "$(uname -s)" in
        Darwin)  # macOS
            port=$(ls -t /dev/tty.usbserial* /dev/tty.SLAB_USBtoUART* /dev/tty.wchusbserial* 2>/dev/null | head -n 1)
            ;;
        Linux)   # Linux
            port=$(ls -t /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -n 1)
            ;;
        MINGW*|MSYS*|CYGWIN*)  # Windows
            port=$(ls -t /dev/ttyS* 2>/dev/null | head -n 1)
            if [ -z "$port" ]; then
                # Alternativa usando PowerShell per Windows
                port=$(powershell.exe -Command "[System.IO.Ports.SerialPort]::getportnames()[0]" 2>/dev/null)
                if [ ! -z "$port" ]; then
                    port="/dev/$port"
                fi
            fi
            ;;
        *)
            echo "Sistema operativo non supportato"
            return 1
            ;;
    esac

    if [ -z "$port" ]; then
        echo "Nessuna porta seriale trovata"
        return 1
    fi

    echo "$port"
    return 0
}

export CMAKE_ROOT="/opt/homebrew/Cellar/cmake/3.31.6/share/cmake"

# Usa la funzione per settare la variabile
export ESP_DEV="/dev/tty.usbserial-1120"

ESP_DEV_found=$(find_serial_port | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,3})*)?[mGK]//g")
if [ $? -eq 0 ]; then
    export ESP_DEV=$ESP_DEV_found
    echo "Porta seriale trovata: $ESP_DEV"
else
    echo "Errore nel trovare la porta seriale"
fi

export C_FLAGS="-fstack-usage"

export MAKEFLAGS="-j8"
export NINJA_JOBS=8
