# luajit-raylib-binding-generator

A LuaJIT binding generator for raylib that automatically creates FFI bindings from raylib headers.

## Usage

Generate a Lua module from one or more raylib C headers:

```bash
python /home/runner/work/luajit-raylib-binding-generator/luajit-raylib-binding-generator/tools/generate_luajit_raylib_bindings.py \
  --header /path/to/raylib/src/raylib.h \
  --output /path/to/project/raylib.lua
```

Options:

- `--header`: Header file to parse. Repeat for multiple headers.
- `--output`: Destination Lua file to generate.
- `--library-name`: Library name used by `ffi.load` (default: `raylib`).

## Output

The generator emits a Lua module that:

- defines all discovered C declarations with `ffi.cdef`
- exports parsed enum constants in `M.enums`
- loads the raylib shared library via `ffi.load`

Example in Lua:

```lua
local raylib = require("raylib")
raylib.C.InitWindow(800, 450, "raylib + LuaJIT")
```
