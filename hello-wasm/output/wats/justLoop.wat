(module $justLoop.wasm
  (type (;0;) (func))
  (type (;1;) (func (param i32)))
  (type (;2;) (func (param i32 i32)))
  (type (;3;) (func (result i32)))
  (import "env" "esp_printf" (func $esp_printf (type 2)))
  (import "env" "memory" (memory (;0;) 1 32768))
  (func $__wasm_call_ctors (type 0))
  (func $print_num (type 1) (param i32)
    (local i32)
    global.get $__stack_pointer
    i32.const 16
    i32.sub
    local.tee 1
    global.set $__stack_pointer
    local.get 1
    local.get 0
    i32.store
    i32.const 1024
    local.get 1
    call $esp_printf
    local.get 1
    i32.const 16
    i32.add
    global.set $__stack_pointer)
  (func $start (type 0)
    (local i32 i32)
    i32.const 0
    local.set 0
    loop  ;; label = @1
      local.get 0
      local.tee 0
      call $print_num
      local.get 0
      i32.const 1
      i32.add
      local.tee 1
      local.set 0
      local.get 1
      i32.const 100
      i32.ne
      br_if 0 (;@1;)
    end)
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
  (func $emscripten_stack_get_current (type 3) (result i32)
    global.get $__stack_pointer)
  (table (;0;) 2 2 funcref)
  (global $__stack_pointer (mut i32) (i32.const 5136))
  (export "start" (func $start))
  (export "__indirect_function_table" (table 0))
  (export "_initialize" (func $_initialize))
  (export "_emscripten_stack_restore" (func $_emscripten_stack_restore))
  (export "emscripten_stack_get_current" (func $emscripten_stack_get_current))
  (elem (;0;) (i32.const 1) func $__wasm_call_ctors)
  (data $.rodata (i32.const 1024) "Num: %d\0a\00"))
