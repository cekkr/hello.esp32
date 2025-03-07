# Follow guide in studies/emulateESP32Qemu.md

# Installa socat se non è già installato
#brew install socat

# Crea una coppia di porte seriali virtuali
#socat -d -d pty,raw,echo=0,link=/tmp/ttyS0 pty,raw,echo=0,link=/tmp/ttyS1 &

source ./hello-idf/espShellEnv.sh

# prepare with: idf.py qemu monitor
~/esp/qemu/build/qemu-system-xtensa -M esp32 -m 4M -drive file=/Users/riccardo/Sources/GitHub/hello.esp32/hello-idf/build/flash_image.bin,if=mtd,format=raw -drive file=/Users/riccardo/Sources/GitHub/hello.esp32/hello-idf/build/qemu_efuse.bin,if=none,format=raw,id=efuse -global driver=nvram.esp32.efuse,property=drive,value=efuse -global driver=timer.esp32.timg,property=wdt_disable,value=true -nic user,model=open_eth -serial tcp::5555,server,nowait \
 -drive file=local/sdcard.img,if=sd,format=raw \
 -L qemu_esp32_lcd.cfg \
 -bios hello-idf/build/hello-idf.elf \

exit

python $IDF_PATH/components/esptool_py/esptool/esptool.py --chip esp32 merge_bin -o flash_image.bin --fill-flash-size 4MB \
0x1000 hello-idf/build/bootloader/bootloader.bin \
0x8000 hello-idf/build/partition_table/partition-table.bin \
0x10000 hello-idf/build/hello-idf.bin

# Avvia QEMU utilizzando una delle porte seriali virtuali
~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -kernel hello-idf/build/hello-idf.elf \
  -L qemu_esp32_lcd.cfg \
  -no-reboot \
  -drive file=flash_image.bin,if=mtd,format=raw \
  -drive file=local/sdcard.img,if=sd,format=raw 

# -serial tcp::5555,server,nowait \
# -monitor telnet:127.0.0.1:1234,server,nowait \

# -drive file=hello-idf/build/hello-idf.bin,if=mtd,format=raw \
# -bios hello-idf/build/bootloader/bootloader.bin \

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