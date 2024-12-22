(module
  (type (;0;) (func))
  (type (;1;) (func (param i32)))
  (type (;2;) (func (param i32 i32)))
  (type (;3;) (func (param i32) (result i32)))
  (type (;4;) (func (result i32)))
  (import "env" "esp_printf" (func (;0;) (type 2)))
  (import "env" "memory" (memory (;0;) 1 32768))
  (func (;1;) (type 0)
    nop)
  (func (;2;) (type 3) (param i32) (result i32)
    (local i32 i32 i32 i32 i32)
    local.get 0
    i32.const 2
    i32.lt_u
    if  ;; label = @1
      local.get 0
      return
    end
    i32.const 1
    local.set 1
    i32.const 3
    local.get 0
    i32.const 1
    i32.add
    local.tee 0
    local.get 0
    i32.const 3
    i32.le_u
    select
    local.tee 2
    i32.const 2
    i32.sub
    local.tee 3
    i32.const 7
    i32.and
    local.set 4
    i32.const 0
    local.set 0
    local.get 2
    i32.const 3
    i32.sub
    i32.const 7
    i32.ge_u
    if  ;; label = @1
      local.get 3
      i32.const -8
      i32.and
      local.set 3
      i32.const 0
      local.set 2
      loop  ;; label = @2
        local.get 0
        local.get 1
        i32.add
        local.tee 0
        local.get 1
        i32.add
        local.tee 1
        local.get 0
        i32.add
        local.tee 0
        local.get 1
        i32.add
        local.tee 1
        local.get 0
        i32.add
        local.tee 0
        local.get 1
        i32.add
        local.tee 1
        local.get 0
        i32.add
        local.tee 0
        local.get 1
        i32.add
        local.set 1
        local.get 2
        i32.const 8
        i32.add
        local.tee 2
        local.get 3
        i32.ne
        br_if 0 (;@2;)
      end
    end
    local.get 4
    if  ;; label = @1
      loop  ;; label = @2
        local.get 0
        local.get 1
        local.tee 0
        i32.add
        local.set 1
        local.get 5
        i32.const 1
        i32.add
        local.tee 5
        local.get 4
        i32.ne
        br_if 0 (;@2;)
      end
    end
    local.get 1)
  (func (;3;) (type 1) (param i32)
    (local i32 i32 i32 i32 i32 i32 i32 i32 i32 i32)
    global.get 0
    i32.const -64
    i32.add
    local.tee 2
    global.set 0
    local.get 2
    local.get 0
    i32.store offset=48
    i32.const 1074
    local.get 2
    i32.const 48
    i32.add
    call 0
    loop  ;; label = @1
      local.get 2
      local.get 5
      local.tee 7
      i32.store offset=32
      i32.const 1039
      local.get 2
      i32.const 32
      i32.add
      call 0
      local.get 5
      i32.const 1
      i32.add
      local.set 5
      block  ;; label = @2
        local.get 7
        local.tee 1
        i32.const 2
        i32.lt_u
        br_if 0 (;@2;)
        i32.const 3
        local.get 5
        local.get 5
        i32.const 3
        i32.le_u
        select
        local.tee 6
        i32.const 2
        i32.sub
        local.tee 3
        i32.const 7
        i32.and
        local.set 8
        i32.const 0
        local.set 9
        i32.const 1
        local.set 1
        i32.const 0
        local.set 4
        local.get 6
        i32.const 3
        i32.sub
        i32.const 7
        i32.ge_u
        if  ;; label = @3
          local.get 3
          i32.const -8
          i32.and
          local.set 6
          i32.const 0
          local.set 10
          loop  ;; label = @4
            local.get 1
            local.get 1
            local.get 4
            i32.add
            local.tee 4
            i32.add
            local.tee 3
            local.get 3
            local.get 4
            i32.add
            local.tee 1
            i32.add
            local.tee 3
            local.get 1
            local.get 3
            i32.add
            local.tee 1
            i32.add
            local.tee 3
            local.get 1
            local.get 3
            i32.add
            local.tee 4
            i32.add
            local.set 1
            local.get 10
            i32.const 8
            i32.add
            local.tee 10
            local.get 6
            i32.ne
            br_if 0 (;@4;)
          end
        end
        local.get 8
        i32.eqz
        br_if 0 (;@2;)
        loop  ;; label = @3
          local.get 4
          local.get 1
          local.tee 3
          i32.add
          local.set 1
          local.get 3
          local.set 4
          local.get 9
          i32.const 1
          i32.add
          local.tee 9
          local.get 8
          i32.ne
          br_if 0 (;@3;)
        end
      end
      local.get 2
      local.get 1
      i32.store offset=16
      i32.const 1024
      local.get 2
      i32.const 16
      i32.add
      call 0
      local.get 2
      local.get 1
      i32.store offset=4
      local.get 2
      local.get 7
      i32.store
      i32.const 1062
      local.get 2
      call 0
      local.get 0
      local.get 5
      i32.ge_u
      br_if 0 (;@1;)
    end
    local.get 2
    i32.const -64
    i32.sub
    global.set 0)
  (func (;4;) (type 0)
    (local i32)
    global.get 0
    i32.const 544
    i32.sub
    local.tee 0
    global.set 0
    local.get 0
    i32.const 10
    i32.store offset=528
    i32.const 1074
    local.get 0
    i32.const 528
    i32.add
    call 0
    local.get 0
    i32.const 0
    i32.store offset=512
    i32.const 1039
    local.get 0
    i32.const 512
    i32.add
    call 0
    local.get 0
    i32.const 0
    i32.store offset=496
    i32.const 1024
    local.get 0
    i32.const 496
    i32.add
    call 0
    local.get 0
    i64.const 0
    i64.store offset=480
    i32.const 1062
    local.get 0
    i32.const 480
    i32.add
    call 0
    local.get 0
    i32.const 1
    i32.store offset=464
    i32.const 1039
    local.get 0
    i32.const 464
    i32.add
    call 0
    local.get 0
    i32.const 1
    i32.store offset=448
    i32.const 1024
    local.get 0
    i32.const 448
    i32.add
    call 0
    local.get 0
    i64.const 4294967297
    i64.store offset=432
    i32.const 1062
    local.get 0
    i32.const 432
    i32.add
    call 0
    local.get 0
    i32.const 2
    i32.store offset=416
    i32.const 1039
    local.get 0
    i32.const 416
    i32.add
    call 0
    local.get 0
    i32.const 1
    i32.store offset=400
    i32.const 1024
    local.get 0
    i32.const 400
    i32.add
    call 0
    local.get 0
    i64.const 4294967298
    i64.store offset=384
    i32.const 1062
    local.get 0
    i32.const 384
    i32.add
    call 0
    local.get 0
    i32.const 3
    i32.store offset=368
    i32.const 1039
    local.get 0
    i32.const 368
    i32.add
    call 0
    local.get 0
    i32.const 2
    i32.store offset=352
    i32.const 1024
    local.get 0
    i32.const 352
    i32.add
    call 0
    local.get 0
    i64.const 8589934595
    i64.store offset=336
    i32.const 1062
    local.get 0
    i32.const 336
    i32.add
    call 0
    local.get 0
    i32.const 4
    i32.store offset=320
    i32.const 1039
    local.get 0
    i32.const 320
    i32.add
    call 0
    local.get 0
    i32.const 3
    i32.store offset=304
    i32.const 1024
    local.get 0
    i32.const 304
    i32.add
    call 0
    local.get 0
    i64.const 12884901892
    i64.store offset=288
    i32.const 1062
    local.get 0
    i32.const 288
    i32.add
    call 0
    local.get 0
    i32.const 5
    i32.store offset=272
    i32.const 1039
    local.get 0
    i32.const 272
    i32.add
    call 0
    local.get 0
    i32.const 5
    i32.store offset=256
    i32.const 1024
    local.get 0
    i32.const 256
    i32.add
    call 0
    local.get 0
    i64.const 21474836485
    i64.store offset=240
    i32.const 1062
    local.get 0
    i32.const 240
    i32.add
    call 0
    local.get 0
    i32.const 6
    i32.store offset=224
    i32.const 1039
    local.get 0
    i32.const 224
    i32.add
    call 0
    local.get 0
    i32.const 8
    i32.store offset=208
    i32.const 1024
    local.get 0
    i32.const 208
    i32.add
    call 0
    local.get 0
    i64.const 34359738374
    i64.store offset=192
    i32.const 1062
    local.get 0
    i32.const 192
    i32.add
    call 0
    local.get 0
    i32.const 7
    i32.store offset=176
    i32.const 1039
    local.get 0
    i32.const 176
    i32.add
    call 0
    local.get 0
    i32.const 13
    i32.store offset=160
    i32.const 1024
    local.get 0
    i32.const 160
    i32.add
    call 0
    local.get 0
    i64.const 55834574855
    i64.store offset=144
    i32.const 1062
    local.get 0
    i32.const 144
    i32.add
    call 0
    local.get 0
    i32.const 8
    i32.store offset=128
    i32.const 1039
    local.get 0
    i32.const 128
    i32.add
    call 0
    local.get 0
    i32.const 21
    i32.store offset=112
    i32.const 1024
    local.get 0
    i32.const 112
    i32.add
    call 0
    local.get 0
    i64.const 90194313224
    i64.store offset=96
    i32.const 1062
    local.get 0
    i32.const 96
    i32.add
    call 0
    local.get 0
    i32.const 9
    i32.store offset=80
    i32.const 1039
    local.get 0
    i32.const 80
    i32.add
    call 0
    local.get 0
    i32.const 34
    i32.store offset=64
    i32.const 1024
    local.get 0
    i32.const -64
    i32.sub
    call 0
    local.get 0
    i64.const 146028888073
    i64.store offset=48
    i32.const 1062
    local.get 0
    i32.const 48
    i32.add
    call 0
    local.get 0
    i32.const 10
    i32.store offset=32
    i32.const 1039
    local.get 0
    i32.const 32
    i32.add
    call 0
    local.get 0
    i32.const 55
    i32.store offset=16
    i32.const 1024
    local.get 0
    i32.const 16
    i32.add
    call 0
    local.get 0
    i64.const 236223201290
    i64.store
    i32.const 1062
    local.get 0
    call 0
    local.get 0
    i32.const 544
    i32.add
    global.set 0)
  (func (;5;) (type 1) (param i32)
    local.get 0
    global.set 0)
  (func (;6;) (type 4) (result i32)
    global.get 0)
  (table (;0;) 2 2 funcref)
  (global (;0;) (mut i32) (i32.const 17488))
  (export "fib" (func 2))
  (export "print_fibonacci" (func 3))
  (export "start" (func 4))
  (export "__indirect_function_table" (table 0))
  (export "_initialize" (func 1))
  (export "_emscripten_stack_restore" (func 5))
  (export "emscripten_stack_get_current" (func 6))
  (elem (;0;) (i32.const 1) func 1)
  (data (;0;) (i32.const 1024) "Got result=%d\0a\00Calling fib with n=%d\0a\00F(%d) = %d\0a\00Fibonacci series up to %d:\0a"))
