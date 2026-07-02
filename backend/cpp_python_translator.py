"""Small rule-based C++ to Python translator for CP-style snippets.

The ML model used by the app is a small pretrained CodeT5 checkpoint, so it is
not reliable as the primary translator. This module handles the common
competitive-programming subset deterministically and returns runnable Python.
"""

from __future__ import annotations

import re


CPP_TYPE_RE = r"(?:long\s+long|int|double|float|string|char|bool)"
INDENT = " " * 4


def translate_competitive_cpp(source_code: str) -> str:
    """Translate a practical subset of C++ into Python.

    The generated program uses token-based stdin reading, which matches most
    competitive-programming input formats and works for both one-line and
    multi-line input.
    """

    translator = _Translator()
    return translator.translate(source_code)


class _Translator:
    def __init__(self) -> None:
        self.variables: dict[str, str] = {}
        self.vectors: dict[str, str] = {}
        self.indent = 1
        self.output: list[str] = [
            "import sys",
            "",
            "",
            "def main():",
            f"{INDENT}data = sys.stdin.read().split()",
            f"{INDENT}it = iter(data)",
        ]

    def translate(self, source_code: str) -> str:
        for raw_line in _normalize_lines(_strip_comments(source_code)):
            self._translate_line(raw_line.strip())

        self.output.extend(
            [
                "",
                "",
                'if __name__ == "__main__":',
                f"{INDENT}main()",
            ]
        )
        return "\n".join(_collapse_blank_lines(self.output)).strip() + "\n"

    def _translate_line(self, line: str) -> None:
        if not line:
            return

        if line == "}":
            self.indent = max(1, self.indent - 1)
            return

        if _should_skip(line):
            return

        if line.startswith("} "):
            self.indent = max(1, self.indent - 1)
            line = line[2:].strip()

        opens_block = line.endswith("{")
        if opens_block:
            line = line[:-1].strip()

        translated = self._convert_header(line) if opens_block else self._convert_statement(line)
        if translated:
            for translated_line in translated:
                self._emit(translated_line)

        if opens_block and translated:
            self.indent += 1

    def _convert_header(self, line: str) -> list[str]:
        line = line.strip()

        range_for = re.fullmatch(
            rf"for\s*\(\s*(?:{CPP_TYPE_RE}\s+)?(\w+)\s*=\s*(.+?)\s*;\s*\1\s*([<>]=?)\s*(.+?)\s*;\s*(.+?)\s*\)",
            line,
        )
        if range_for:
            var, start, op, end, step_expr = range_for.groups()
            start = _convert_expression(start)
            end = _convert_expression(end)
            step = _loop_step(var, step_expr)

            if op in ("<", "<="):
                stop = end if op == "<" else f"({end}) + 1"
                if start == "0" and step == "1":
                    return [f"for {var} in range({stop}):"]
                if step == "1":
                    return [f"for {var} in range({start}, {stop}):"]
                return [f"for {var} in range({start}, {stop}, {step}):"]

            stop = end if op == ">" else f"({end}) - 1"
            if step == "-1":
                return [f"for {var} in range({start}, {stop}, -1):"]

        each_for = re.fullmatch(
            rf"for\s*\(\s*(?:const\s+)?(?:{CPP_TYPE_RE}|auto)\s*&?\s*(\w+)\s*:\s*(.+?)\s*\)",
            line,
        )
        if each_for:
            var, iterable = each_for.groups()
            return [f"for {var} in {_convert_expression(iterable)}:"]

        if_match = re.fullmatch(r"if\s*\((.*)\)", line)
        if if_match:
            return [f"if {_convert_expression(if_match.group(1))}:"]

        elif_match = re.fullmatch(r"else\s+if\s*\((.*)\)", line)
        if elif_match:
            return [f"elif {_convert_expression(elif_match.group(1))}:"]

        if line == "else":
            return ["else:"]

        while_match = re.fullmatch(r"while\s*\((.*)\)", line)
        if while_match:
            return [f"while {_convert_expression(while_match.group(1))}:"]

        return [_convert_expression(line) + ":"]

    def _convert_statement(self, line: str) -> list[str]:
        line = line.rstrip(";").strip()

        if _should_skip(line):
            return []

        vector_decl = re.fullmatch(rf"vector\s*<\s*({CPP_TYPE_RE})\s*>\s+(\w+)\s*\((.*?)\)", line)
        if vector_decl:
            cpp_type, name, args = vector_decl.groups()
            self.vectors[name] = cpp_type
            parts = [part.strip() for part in args.split(",") if part.strip()]
            if not parts:
                return [f"{name} = []"]
            size = _convert_expression(parts[0])
            fill = _convert_expression(parts[1]) if len(parts) > 1 else _zero_value(cpp_type)
            return [f"{name} = [{fill}] * ({size})"]

        vector_initializer = re.fullmatch(rf"vector\s*<\s*({CPP_TYPE_RE})\s*>\s+(\w+)\s*=\s*\{{(.*)\}}", line)
        if vector_initializer:
            cpp_type, name, values = vector_initializer.groups()
            self.vectors[name] = cpp_type
            return [f"{name} = [{_convert_expression(values)}]"]

        declaration = re.fullmatch(rf"({CPP_TYPE_RE})\s+(.+)", line)
        if declaration:
            cpp_type, rest = declaration.groups()
            return self._convert_declaration(cpp_type, rest)

        if line.startswith("cin"):
            return self._convert_cin(line)

        if line.startswith("cout"):
            return self._convert_cout(line)

        push_back = re.fullmatch(r"(\w+)\.push_back\((.*)\)", line)
        if push_back:
            name, value = push_back.groups()
            return [f"{name}.append({_convert_expression(value)})"]

        return [_convert_expression(line)]

    def _convert_declaration(self, cpp_type: str, rest: str) -> list[str]:
        translated: list[str] = []
        for part in _split_top_level(rest, ","):
            part = part.strip()
            name_match = re.match(r"(\w+)", part)
            if not name_match:
                continue

            name = name_match.group(1)
            self.variables[name] = cpp_type

            if "=" in part:
                name, value = [piece.strip() for piece in part.split("=", 1)]
                translated.append(f"{name} = {_convert_expression(value)}")

        return translated

    def _convert_cin(self, line: str) -> list[str]:
        targets = [part.strip() for part in line.split(">>")[1:]]
        translated: list[str] = []

        for target in targets:
            target = target.strip()
            if not target:
                continue

            base_name = target.split("[", 1)[0].strip()
            cpp_type = self.vectors.get(base_name) if "[" in target else self.variables.get(base_name, "int")
            translated.append(f"{target} = {_reader_for_type(cpp_type)}")

        return translated

    def _convert_cout(self, line: str) -> list[str]:
        parts = [part.strip() for part in line.split("<<")[1:]]
        expressions: list[str] = []
        pending_space = False

        for part in parts:
            literal = _string_literal_value(part)
            if part == "endl" or literal in {r"\n", r"\\n"}:
                continue
            if literal == " ":
                pending_space = True
                continue

            expression = _convert_expression(part)
            expressions.append(expression)

        if not expressions:
            return ["print()"]

        if pending_space:
            return [f"print({', '.join(expressions)})"]

        if len(expressions) == 1:
            return [f"print({expressions[0]})"]

        joined = " + ".join(f"str({expression})" for expression in expressions)
        return [f"print({joined})"]

    def _emit(self, line: str) -> None:
        self.output.append(f"{INDENT * self.indent}{line}")


def _strip_comments(source_code: str) -> str:
    source_code = re.sub(r"/\*.*?\*/", "", source_code, flags=re.DOTALL)
    return re.sub(r"//.*", "", source_code)


def _normalize_lines(source_code: str) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escape = False

    for char in source_code:
        if quote:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue

        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)

        if char == "{":
            current.append(char)
            _push_current(lines, current)
        elif char == "}":
            _push_current(lines, current)
            lines.append("}")
        elif char == ";" and depth == 0:
            _push_current(lines, current)
        elif char == "\n":
            _push_current(lines, current)
        else:
            current.append(char)

    _push_current(lines, current)
    return lines


def _push_current(lines: list[str], current: list[str]) -> None:
    line = "".join(current).strip()
    current.clear()
    if line:
        lines.append(line)


def _should_skip(line: str) -> bool:
    return (
        line.startswith("#")
        or line == "using namespace std"
        or line.startswith("int main(")
        or line.startswith("signed main(")
        or line.startswith("ios::sync_with_stdio")
        or line.startswith("cin.tie")
        or line.startswith("cout.tie")
        or line.startswith("return 0")
    )


def _convert_expression(expression: str) -> str:
    expression = expression.strip().rstrip(";")
    expression = expression.replace("std::", "")
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", "not ", expression)
    expression = re.sub(r"\btrue\b", "True", expression)
    expression = re.sub(r"\bfalse\b", "False", expression)
    expression = re.sub(r"\bNULL\b|\bnullptr\b", "None", expression)
    expression = re.sub(r"\((?:long\s+long|int|double|float|string|char|bool)\)", "", expression)
    expression = re.sub(r"(\w+)\.(?:size|length)\(\)", r"len(\1)", expression)
    expression = re.sub(r"(\w+)\+\+$", r"\1 += 1", expression)
    expression = re.sub(r"(\w+)--$", r"\1 -= 1", expression)
    return expression.strip()


def _loop_step(var: str, step_expr: str) -> str:
    step_expr = step_expr.replace(" ", "")
    if step_expr in {f"{var}++", f"++{var}"}:
        return "1"
    if step_expr in {f"{var}--", f"--{var}"}:
        return "-1"

    plus_equal = re.fullmatch(rf"{var}\+=(.+)", step_expr)
    if plus_equal:
        return _convert_expression(plus_equal.group(1))

    minus_equal = re.fullmatch(rf"{var}-=(.+)", step_expr)
    if minus_equal:
        return f"-({_convert_expression(minus_equal.group(1))})"

    return "1"


def _reader_for_type(cpp_type: str | None) -> str:
    if cpp_type in {"double", "float"}:
        return "float(next(it))"
    if cpp_type in {"string", "char"}:
        return "next(it)"
    if cpp_type == "bool":
        return "bool(int(next(it)))"
    return "int(next(it))"


def _zero_value(cpp_type: str) -> str:
    if cpp_type in {"double", "float"}:
        return "0.0"
    if cpp_type in {"string", "char"}:
        return '""'
    if cpp_type == "bool":
        return "False"
    return "0"


def _string_literal_value(value: str) -> str | None:
    value = value.strip()
    if len(value) < 2 or value[0] not in {"'", '"'} or value[-1] != value[0]:
        return None
    return value[1:-1]


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for char in value:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)

        if char == delimiter and depth == 0:
            parts.append("".join(current))
            current.clear()
        else:
            current.append(char)

    parts.append("".join(current))
    return parts


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = blank
    return collapsed
