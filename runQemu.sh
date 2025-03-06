# Follow guide in studies/emulateESP32Qemu.md

~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -nographic \
  -serial stdio \
  -kernel hello-idf/build/hello-idf.elf \
  -monitor telnet:127.0.0.1:1234,server,nowait \
  -d in_asm,cpu,guest_errors,unimp \
  -s -S

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