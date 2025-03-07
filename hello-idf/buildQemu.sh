source ./espShellEnv.sh

idf.py set-target esp32
idf.py build -DIDF_TARGET_QEMU=1