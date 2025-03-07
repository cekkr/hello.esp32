# Follow guide in studies/emulateESP32Qemu.md

# Installa socat se non è già installato
#brew install socat

# Crea una coppia di porte seriali virtuali
#socat -d -d pty,raw,echo=0,link=/tmp/ttyS0 pty,raw,echo=0,link=/tmp/ttyS1 &

# Avvia QEMU utilizzando una delle porte seriali virtuali
~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -serial stdio \
  -monitor telnet:127.0.0.1:1234,server,nowait \
  -kernel hello-idf/build/hello-idf.elf

# Connect through: screen /tmp/ttyS0 115200

# source ./hello-idf/espShellEnv.sh
# xtensa-esp32-elf-gdb hello-idf/build/hello-idf.elf

#   -nographic \
#  -loadvm/xtensa-soft-mmu \

echo ~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -drive file=local/sdcard.img,if=sd,format=raw \
  -display sdl \
  -cpu esp32 \
  -no-reboot \
  -L qemu_esp32_lcd.cfg \
  -serial stdio \
  -kernel hello-idf/build/hello-idf.elf