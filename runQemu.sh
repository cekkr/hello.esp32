# Follow guide in studies/emulateESP32Qemu.md
~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -drive file=local/sdcard.img,if=sd,format=raw \
  -display sdl \
  -cpu esp32 \
  -nographic \
  -no-reboot \
  -L qemu_esp32_lcd.cfg \
  -kernel hello-idf/build/hello-idf.elf

  #  -loadvm/xtensa-soft-mmu \