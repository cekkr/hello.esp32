# Follow guide in studies/emulateESP32Qemu.md

# END OF THE LINE: for the moment i'm not able to create an emulable build of the project

# Installa socat se non è già installato
#brew install socat

# Crea una coppia di porte seriali virtuali
#socat -d -d pty,raw,echo=0,link=/tmp/ttyS0 pty,raw,echo=0,link=/tmp/ttyS1 &

source ./hello-idf/espShellEnv.sh

# prepare with: idf.py qemu monitor
echo ~/esp/qemu/build/qemu-system-xtensa -M esp32 -m 4M -drive file=hello-idf/build/flash_image.bin,if=mtd,format=raw -drive file=hello-idf/build/qemu_efuse.bin,if=none,format=raw,id=efuse -global driver=nvram.esp32.efuse,property=drive,value=efuse -global driver=timer.esp32.timg,property=wdt_disable,value=true -nic user,model=open_eth -serial tcp::5555,server,nowait \
 -drive file=local/sdcard.img,if=sd,format=raw \
 -L qemu_esp32_lcd.cfg \
 -bios hello-idf/build/hello-idf.elf \

python $IDF_PATH/components/esptool_py/esptool/esptool.py --chip esp32 \
merge_bin -o flash_image.bin \
--flash_mode dio --flash_freq 40m --flash_size 4MB \
0x1000 hello-idf/build/bootloader/bootloader.bin \
0x8000 hello-idf/build/partition_table/partition-table.bin \
0x10000 hello-idf/build/hello-idf.bin

# Crea un file vuoto di 4MB
dd if=/dev/zero of=flash_image_padded.bin bs=1M count=4

# Copia il contenuto dell'immagine originale nell'immagine padded
dd if=flash_image.bin of=flash_image_padded.bin conv=notrunc

~/esp/qemu/build/qemu-system-xtensa -M esp32 -m 4M -drive file=flash_image_padded.bin,if=mtd,format=raw -drive file=/Users/riccardo/Sources/GitHub/hello.esp32/hello-idf/build/qemu_efuse.bin,if=none,format=raw,id=efuse -global driver=nvram.esp32.efuse,property=drive,value=efuse -global driver=timer.esp32.timg,property=wdt_disable,value=true -nic user,model=open_eth -nographic -serial tcp::5555,server,nowait -no-reboot

# Avvia QEMU utilizzando una delle porte seriali virtuali
echo ~/esp/qemu/build/qemu-system-xtensa \
  -machine esp32 \
  -m 4M \
  -bios hello-idf/build/bootloader/bootloader.elf \
  -drive file=flash_image_padded.bin,if=mtd,format=raw \
  -L qemu_esp32_lcd.cfg \
  -no-reboot \
  -drive file=local/sdcard.img,if=sd,format=raw \
  -serial stdio \
  -display sdl \
  -monitor telnet:127.0.0.1:5555,server,nowait \
  -d guest_errors,unimp,int

#  -drive file=flash_image.bin,if=mtd,format=raw \

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