(module $fibonacciPrint.wasm
  (type (;0;) (func))
  (type (;1;) (func (param i32)))
  (type (;2;) (func (param i32 i32)))
  (type (;3;) (func (param i32) (result i32)))
  (type (;4;) (func (result i32)))
  (import "env" "esp_printf" (func $esp_printf (type 2)))
  (import "env" "memory" (memory (;0;) 1 32768))
  (func $__wasm_call_ctors (type 0))
  (func $fib (type 3) (param i32) (result i32)
    (local i32 i32 i32 i32 i32 i32)
    block  ;; label = @1
      local.get 0
      i32.const 2
      i32.ge_u
      br_if 0 (;@1;)
      local.get 0
      return
    end
    local.get 0
    i32.const 1
    i32.add
    local.tee 0
    i32.const 3
    local.get 0
    i32.const 3
    i32.gt_u
    select
    local.set 1
    i32.const 2
    local.set 0
    i32.const 1
    local.set 2
    i32.const 0
    local.set 3
    loop  ;; label = @1
      local.get 0
      i32.const 1
      i32.add
      local.tee 4
      local.set 0
      local.get 2
      local.tee 5
      local.get 3
      i32.add
      local.tee 6
      local.set 2
      local.get 5
      local.set 3
      local.get 6
      local.set 5
      local.get 4
      local.get 1
      i32.ne
      br_if 0 (;@1;)
    end
    local.get 5)
  (func $print_fibonacci (type 1) (param i32)
    (local i32 i32 i32)
    global.get $__stack_pointer
    i32.const 64
    i32.sub
    local.tee 1
    global.set $__stack_pointer
    local.get 1
    local.get 0
    i32.store offset=48
    i32.const 1074
    local.get 1
    i32.const 48
    i32.add
    call $esp_printf
    i32.const 0
    local.set 2
    loop  ;; label = @1
      local.get 1
      local.get 2
      local.tee 2
      i32.store offset=32
      i32.const 1039
      local.get 1
      i32.const 32
      i32.add
      call $esp_printf
      local.get 1
      local.get 2
      call $fib
      local.tee 3
      i32.store offset=16
      i32.const 1024
      local.get 1
      i32.const 16
      i32.add
      call $esp_printf
      local.get 1
      local.get 3
      i32.store offset=4
      local.get 1
      local.get 2
      i32.store
      i32.const 1062
      local.get 1
      call $esp_printf
      local.get 2
      i32.const 1
      i32.add
      local.tee 3
      local.set 2
      local.get 3
      local.get 0
      i32.le_u
      br_if 0 (;@1;)
    end
    local.get 1
    i32.const 64
    i32.add
    global.set $__stack_pointer)
  (func $start (type 0)
    i32.const 10
    call $print_fibonacci)
  (func $_initialize (type 0)
    block  ;; label = @1
      i32.const 1
      i32.eqz
      br_if 0 (;@1;)
      call $__wasm_call_ctors
    end)
  (func $_emscripten_stack_restore (type 1) (param i32)
    local.get 0
    global.set $__stack_pointer)
  (func $emscripten_stack_get_current (type 4) (result i32)
    global.get $__stack_pointer)
  (table (;0;) 2 2 funcref)
  (global $__stack_pointer (mut i32) (i32.const 17488))
  (export "start" (func $start))
  (export "_initialize" (func $_initialize))
  (export "__indirect_function_table" (table 0))
  (export "_emscripten_stack_restore" (func $_emscripten_stack_restore))
  (export "emscripten_stack_get_current" (func $emscripten_stack_get_current))
  (elem (;0;) (i32.const 1) func $__wasm_call_ctors)
  (data $.rodata (i32.const 1024) "Got result=%d\0a\00Calling fib with n=%d\0a\00F(%d) = %d\0a\00Fibonacci series up to %d:\0a\00"))
