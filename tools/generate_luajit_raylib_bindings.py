#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


API_MACROS = (
    "RLAPI",
    "RMAPI",
    "RAYGUIDEF",
    "RAYMATHAPI",
)


def strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//.*", "", source)
    return source


def normalize_header(source: str) -> str:
    source = strip_comments(source)
    source = re.sub(r'extern\s+"C"\s*\{', "", source)
    source = re.sub(r"^\s*#.*$", "", source, flags=re.MULTILINE)
    source = re.sub(r"__attribute__\s*\(\(.*?\)\)", "", source, flags=re.DOTALL)
    for macro in API_MACROS:
        source = re.sub(rf"\b{macro}\b", "", source)
    source = re.sub(r"\b__declspec\s*\(.*?\)", "", source)
    source = re.sub(r"\r\n?", "\n", source)
    return source


def collect_c_declarations(source: str) -> str:
    declarations: list[str] = []
    chunk: list[str] = []
    brace_depth = 0

    for char in source:
        chunk.append(char)
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(brace_depth - 1, 0)
        elif char == ";" and brace_depth == 0:
            statement = "".join(chunk).strip()
            chunk.clear()
            if not statement:
                continue
            if "static inline" in statement:
                continue
            if statement in (";",):
                continue
            declarations.append(statement)

    return "\n".join(declarations)


def _safe_eval_int_expression(expr: str, known: dict[str, int]) -> int | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.LShift,
        ast.RShift,
        ast.BitOr,
        ast.BitXor,
        ast.BitAnd,
        ast.Invert,
        ast.USub,
        ast.UAdd,
    )

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            return None
        if isinstance(node, ast.Name) and node.id not in known:
            return None

    try:
        value = eval(compile(tree, "<enum>", "eval"), {"__builtins__": {}}, known)
    except Exception:
        return None

    if not isinstance(value, (int, float)):
        return None
    return int(value)


def extract_enum_constants(source: str) -> dict[str, int]:
    constants: dict[str, int] = {}
    enum_pattern = re.compile(
        r"typedef\s+enum\s+\w*\s*\{(.*?)\}\s*\w+\s*;",
        re.DOTALL,
    )

    for body in enum_pattern.findall(source):
        current: int | None = -1
        for raw_entry in body.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            if "=" in entry:
                name, raw_value = (part.strip() for part in entry.split("=", 1))
                evaluated = _safe_eval_int_expression(raw_value, constants)
                if evaluated is None:
                    current = None
                    continue
                constants[name] = evaluated
                current = evaluated
            else:
                if current is None:
                    continue
                current += 1
                constants[entry] = current

    return constants


def render_lua_module(cdefs: str, constants: dict[str, int], library_name: str) -> str:
    enum_lines = [f"    {name} = {value}," for name, value in sorted(constants.items())]
    enum_block = "\n".join(enum_lines) if enum_lines else ""

    return f"""local ffi = require("ffi")

ffi.cdef[[
{cdefs}
]]

local M = {{}}

M.enums = {{
{enum_block}
}}

M.C = ffi.load("{library_name}")

return M
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LuaJIT raylib bindings from one or more C header files."
    )
    parser.add_argument(
        "--header",
        dest="headers",
        action="append",
        required=True,
        help="Path to a header file to parse. Repeat for multiple headers.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the generated Lua module file.",
    )
    parser.add_argument(
        "--library-name",
        default="raylib",
        help='Shared library name passed to ffi.load (default: "raylib").',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    merged = []
    for header in args.headers:
        header_path = Path(header)
        merged.append(header_path.read_text(encoding="utf-8"))
    merged_source = "\n".join(merged)

    normalized = normalize_header(merged_source)
    cdefs = collect_c_declarations(normalized)
    constants = extract_enum_constants(normalized)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_lua_module(cdefs=cdefs, constants=constants, library_name=args.library_name),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
