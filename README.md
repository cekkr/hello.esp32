# HELLO ESP32!
HelloESP is a sub(operating system) built on the basis of UNIX-like POSIX libraries of ESP-IDF environment that aims to provide a shell for ESP32 systems with SD card support. 

Well, let's go in order.

Some time ago I bought this thing:
![](https://github.com/cekkr/hello.esp32/blob/main/md-assets/product.jpg?raw=true)

It's an ESP32 with a TFT with resistive touch and SD card support. And it's an ESP32, so bluetooth, Wi-Fi etc. Anyway this lacks of PSRAM support. But patience, I always had a dream about to create a sort of OS for Arduino with touch and SD card support, using every component to achieve the maximum functionality possible. The problem is that if you pay poor, you get poor quality. And I never managed to get SD to work on that shield. 

I had to accept reality, but after years of psychotherapy I found this other cheap component that really has a lot to offer: 2 cores, 240 mhz and circa 340 kb of RAM, so much more respect than an Arduino classic.

But even in this case I'm talking about a cheap component, and the examples about its development that I found was only in chinese, and that was my first time with the ESP-IDF environment.

So I stolen the project structure from very honest GitHub repos named like "ESP32-Cheap-Yellow-Display". Because it doesn't need a name, it's just that cheap yellow thing used only by middle school students and me. 

Anyway, seen that I see the opportunities in every part of my poverty, I interpreted the lack of PSRAM as an opportunity to make things as more optimized as possible.

Anyway, in the above mentioned repository are present examples about usages of [basics and the use various programming languages](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/tree/main/Examples): Rust, MicroPython, LVGL and blah blah blah. But my idea was different.

## Hello WASM3!
I wanted to make every kind of programming language portable on the HelloESP, even if are anyway necessary the implementation of the native POSIX-like functions. 

But let's take it one step at a time.

***First of all, a note about the WASM3 developer***: he suffered of the strike of air bomb over his house during the russian invasion, and this makes the repository [wasm3](https://github.com/wasm3/wasm3) 

My fork, [wasm3-helloesp](https://github.com/cekkr/wasm3-helloesp), it's very off-road respect the main repo at the moment. For example, while messing with circular references, during a desperation moment I've substitute some `#ifndef WASM_FILE_H` with `#pragma once` randomly.
There are a lot of python scripts in the folder analyze/ that aims only to build the best circular reference order for the project. The last script I tried finally worked, only I don't remember what of those ones. But I let them there for reference due to the fact that, sometimes, it's still useful have a C project parser using libclang.

### M3Memory is the new black
Anyway, this is an useful training for the creation of a "menuconfig.py" script to allow HelloESP to work on every ESP32 components configuration possible, as long as there is SD reader support. The reason, beyond the fact that it's necessary to store data and binaries, is that the SD card would work as memory paging system. And WASM binaries are perfect for that: the possibility to trace every memory operation let me to create a segmented memory with the support, HelloESP side, of paging of these segments on the SD card. On my device, currently I'm working at 20 MHz of ticks/s with the SD card reader, that allows me to 2 MB/s of writing and reading process for the less used and now needed segments. Due to this particular extension, I've create ad hoc files [`m3_segmented_memory.c`](https://github.com/cekkr/wasm3-helloesp/blob/main/source/m3_segmented_memory.h), in addition to `m3_pointers.c`. Was needed a particular study and reimplementation of various functions and macros around WASM3 source codes. I don't know how much some of that was unnecessary, seen that if I had looked at `m3_api_tracer.c` I would have found out that some achievement may were simpler than than it seemed.

But it doesn't care: a deep study of WASM3 source code was essential, even if it took something like 3 weeks of coding without being able to perform it, I finally found a certain equilibrium in the development line of the project.

Essentialy, if WASM3 when calls `RunCode` use as arguments the macro:

```c
# define d_m3BaseOpSig                  pc_t _pc, m3stack_t _sp, M3MemoryHeader * _mem, m3reg_t _r0
```

WASM3-HelloESP has as base arguments:

```c
# define d_m3BaseOpSig                  pc_t _pc, m3stack_t _sp, M3Memory * _mem, m3reg_t _r0
```

`M3MemoryHeader` is **deprecated** and M3Memory is used instead directly. Several macros are used to combine various combinations of memory allocation. This could be seen directly in function `m3_NewRuntime` in `m3_env.c`:

```c
#if M3Runtime_Stack_Segmented
    runtime->originStack = m3_Malloc (memory, i_stackSizeInBytes + 4 * sizeof (m3slot_t)); 
#else
	runtime->originStack = m3_Def_Malloc (stackSize); // default malloc
#endif 
```

Where `m3_Malloc` works on M3Memory segmentation, instead `m3_Def_Malloc` is the default malloc function, even if reimplemented as `default_malloc` in `m3_core.c` to have a better handling of heap memory management on ESP32.

Anyway, all these experimentations, implementation and modifications mades WASM3-HelloESP currently not mergeable with original WASM3 repo. Anyway, this would be achieve in a second moment with the stabilization of the subsystem.

## HelloESP.Terminal
![](https://github.com/cekkr/hello.esp32/blob/main/md-assets/hello-terminal.jpg?raw=true)

[HelloESP.Terminal](https://github.com/cekkr/helloesp.terminal) is a python GTK GUI program that I use to develop and test the various system features.

In this screenshot, is still evident the italian footprint on the project, but I'll translate labels ASAP. Anyway, I want to use this screenshot to explain the time line of the project development.

The first challenge was to make working SD card reader and TFT screen at the same time. This could be sound very stupid for an expert ESP developer, but that was my first time. And I guess passed a lot of time since the last time I coded in C. 

Then, I developed the basic serial commands that, as seen at the right-top panel of the window, allows me to update the current SD's mount point files list, to upload a file, to delete it and theoretically download it again. Yes, I never tried it. 

Then, I developed the commands system. If the first text box under the terminal is the "raw input", the second text box is for the "shell input". This allows to execute the functions currently implemented in [`he_cmd.h`](https://github.com/cekkr/hello.esp32/blob/main/hello-idf/main/he_cmd.h).

At the moment of writing this test, the command help replies with:

```
$ help
I (03:13:52.285) HELLOESP: Available commands:
I (03:13:52.288) HELLOESP:   - run
I (03:13:52.290) HELLOESP:   - echo
I (03:13:52.292) HELLOESP:   - ls
I (03:13:52.295) HELLOESP:   - restart
I (03:13:52.297) HELLOESP:   - core_dump
I (03:13:52.300) HELLOESP:   - devinfo
I (03:13:52.302) HELLOESP:   - help
```

Anyway the `shell_t` struct already supports the `cwd` storing (by default the `SD_MOUNT_POINT`), so it's already technically possible navigate through the directories.

The "Show Traceback" allows to paste a backtrace line to convert the addresses to the source code files and lines. This is made automatically when it's received through the serial and printed on the terminal text view. Setting the project folder, is possible also to build and flash the project on the run, without disconnecting and reconnecting to the serial port. 

On the left-bottom there is the Task Monitor, that are special serial lines sent by the `he_monitor.c` task, allowing to have in real time informations about the system and running tasks without interference with the main terminal view. 

## Esposed native functions to WASM

Currently, only few WASI native functions are implemented, the fundamental twos: `args_get` and `args_sizes_get`. Anyway, it's essential to implement every of them to achieve a realistic porting of important GNU applications on HelloESP. The native function are compiled in the WASM3 environment using the brand-new function `RegisterWasmFunctions` through the structure:

```c
typedef struct {
    const char* name;  			// Function's name
    void* func;     			// Function's pointer
    const char* signature;  	// Function's signature
} WasmFunctionEntry;
```

The HelloESP native functions signatures are generated following the description `hello-wasm/bindings/esp_wasm.h`, that can be directly referenced by a C code to be compiled in emscripten, where using `hello-wasm/bindingsGenerator.py` generates also the bindings for **TypeScript** and **Rust** (todo: **AssemblyScript**).

At the same directory is available the script `compile.sh`, the compiles in WASM every C file found in `samples/` directory, with an example of a TypeScript to wasm compilation.

It's fundamental the right configuration of emscripten for the right execution of the programs in WASM3 on ESP32: 

```sh
emcc "samples/${script_name}.c" -o "output/${script_name}.wasm" \
        -s WASM=1 \
        -s STANDALONE_WASM=0 \
        -s IMPORTED_MEMORY=1 \
        -s STACK_SIZE=${stack_size} \
        -s ALLOW_MEMORY_GROWTH=1 \
        -s EXPORTED_FUNCTIONS='["_start"]' \
        --no-entry \
        -O1 \
        -fno-inline 
```
It's fundamental to use a low level optimization (**`-O1`**): infact in the case of a simple fibonacci cycle execution, a too high optimization used to calculate automatically the series of numbers, where the next cycle were executed by using calls of over calls, making the ESP32 to crash at the recursive sub stack number 75 circa. Command `wasm2wat` could be used to make readable the output wasm and discover the trick. 

Currently implemented HelloESP native functions in `esp_wasm.h`:

```c
extern void esp_printf(const char* format, ...)  __attribute__((import_module("env"), import_name("esp_printf")));

extern void lcd_draw_text(int x, int y, int size, const char* text)  __attribute__((import_module("env"), import_name("lcd_draw_text")));

extern int esp_add(int a, int b)  __attribute__((import_module("env"), import_name("esp_add")));

extern char* esp_read_serial()  __attribute__((import_module("env"), import_name("esp_read_serial")));
```

As you can see, they're associated to the module named "env". 

This is an example of C wasm program `testSerialRead.wasm`:

```c
#include "esp_wasm.h"

void start() {
    esp_printf("Write something: \n");
    char* res = esp_read_serial(); // write on the command text box
    esp_printf("You wrote: %s\n", res);    
    //todo: ironically, you can't free(res) after using it (not implemented)
    // anyway, a sort of garbage collector is studyable    
}
```

## Current default parameters
| Parameter    | Default value |
| -------- | ------- |
| WASM stack size  | 32 KB    |
| M3Memory segment size | 4096 bytes     |
| Pointers (offset) type    | uint64    |

## Considerations
It's obvious that 2 MB/s of speed of paging could be a certain bottleneck for the execution of complex wasm binaries or their concurrencies to the goal of running a complete operating system with a graphical interface. It's fundamental to create a WASM3 tasks' scheduler highly efficient, also on choosing the best order and distribution to achieve a smooth execution.

Finally, SD cards have the obvious write cycle limits, so it's essential to create an effective system of distributing and relocating pages to different sectors of the FAT32 partition.

### Documentation
I finally made a README, but it's necessary a more structured documentation about how works HelloESP. Anyway, at the moment I'm at the 20% of progress in the development of the project, so many things could change (and complicate). 

## Credits

Made by Riccardo Cecchini (cekkr) 