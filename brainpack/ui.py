"""Small ANSI presentation helpers for Brainpack terminal output."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable

_NO_COLOR = os.getenv("NO_COLOR") is not None


def _supports_color() -> bool:
    return not _NO_COLOR and getattr(sys.stdout, "isatty", lambda: False)()


def _wrap(code: str, text: str) -> str:
    if not _supports_color():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def bold(text: str) -> str:
    return _wrap("1", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def cyan(text: str) -> str:
    return _wrap("36", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def red(text: str) -> str:
    return _wrap("31", text)


def render_header(*, version: str, step: str, subtitle: str | None = None) -> list[str]:
    lines = [f"  {cyan('<>')} {bold('Brainpack')} {dim(f'v{version}')}", ""]
    lines.append(f"  {bold(step)}")
    if subtitle:
        lines.append(f"  {dim(subtitle)}")
    return lines


def render_meta(lines: Iterable[str]) -> list[str]:
    return [f"  {dim(line)}" for line in lines]


def render_rows(rows: Iterable[tuple[str, str]]) -> list[str]:
    rows = list(rows)
    width = max((len(label) for label, _ in rows), default=0)
    return [f"  {dim(label.ljust(width))}  {value}" for label, value in rows]


def render_review(title: str, rows: Iterable[tuple[str, str]]) -> list[str]:
    lines = [f"  {bold(title)}"]
    lines.extend(render_rows(rows))
    return lines


def render_status(title: str, body: Iterable[str], *, tone: str = "info") -> list[str]:
    icon = {"info": dim("->"), "success": green("OK"), "warn": yellow("!"), "error": red("x")}.get(tone, dim("->"))
    body = list(body)
    lines = [f"  {icon} {bold(title)}"]
    lines.extend([f"  {line}" for line in body])
    return lines
