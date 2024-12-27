(module
  (type (;0;) (func))
  (type (;1;) (func (param i32)))
  (type (;2;) (func (param i32 i32)))
  (type (;3;) (func (result i32)))
  (import "env" "esp_printf" (func (;0;) (type 2)))
  (import "env" "memory" (memory (;0;) 256 32768))
  (func (;1;) (type 0))
  (func (;2;) (type 1) (param i32)
    (local i32)
    global.get 0
    i32.const 16
    i32.sub
    local.tee 1
    global.set 0
    local.get 1
    local.get 0
    i32.store
    i32.const 1024
    local.get 1
    call 0
    local.get 1
    i32.const 16
    i32.add
    global.set 0)
  (func (;3;) (type 0)
    (local i32 i32)
    i32.const 0
    local.set 0
    loop  ;; label = @1
      local.get 0
      local.tee 0
      call 2
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
  (func (;4;) (type 0)
    block  ;; label = @1
      i32.const 1
      i32.eqz
      br_if 0 (;@1;)
      call 1
    end)
  (func (;5;) (type 1) (param i32)
    local.get 0
    global.set 0)
  (func (;6;) (type 3) (result i32)
    global.get 0)
  (table (;0;) 2 2 funcref)
  (global (;0;) (mut i32) (i32.const 5136))
  (export "start" (func 3))
  (export "_initialize" (func 4))
  (export "__indirect_function_table" (table 0))
  (export "_emscripten_stack_restore" (func 5))
  (export "emscripten_stack_get_current" (func 6))
  (elem (;0;) (i32.const 1) func 1)
  (data (;0;) (i32.const 1024) "Num: %d\0a\00"))
