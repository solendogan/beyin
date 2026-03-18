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
    lines = [f"  {bold('Brainpack')} {dim(f'v{version}')}", ""]
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


def _visible_len(text: str) -> int:
    """Return printable length of text, stripping ANSI escape codes."""
    import re
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


visible_len = _visible_len  # public alias


def _pad(text: str, width: int) -> str:
    """Pad text to visible width, accounting for ANSI codes."""
    return text + " " * max(0, width - _visible_len(text))


def render_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    max_col_widths: list[int] | None = None,
) -> list[str]:
    """Render a multi-column table with auto-sized columns."""
    if not rows:
        return []
    n = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row[:n]):
            widths[i] = max(widths[i], _visible_len(cell))
    if max_col_widths:
        widths = [min(w, m) for w, m in zip(widths, max_col_widths)]

    def _fmt(cells: list[str]) -> str:
        parts = [_pad(c[:widths[i]], widths[i]) for i, c in enumerate(cells[:n])]
        return "  " + "  ".join(parts).rstrip()

    sep = "  " + "  ".join(dim("─" * w) for w in widths)
    lines = [_fmt([dim(h) for h in headers]), sep]
    for row in rows:
        truncated = [
            c[:widths[i]] + dim("…") if _visible_len(c) > widths[i] else c
            for i, c in enumerate(row[:n])
        ]
        lines.append(_fmt(truncated))
    return lines


def render_status(title: str, body: Iterable[str], *, tone: str = "info") -> list[str]:
    icon = {"info": dim("->"), "success": green("OK"), "warn": yellow("!"), "error": red("x")}.get(tone, dim("->"))
    body = list(body)
    lines = [f"  {icon} {bold(title)}"]
    lines.extend([f"  {line}" for line in body])
    return lines


# ── Box drawing ───────────────────────────────────────────────────────────────

def box_top(label: str, width: int) -> str:
    """Top edge with embedded label: ┌─ label ──...──┐"""
    label_part = f"─ {label} "
    fill = "─" * max(0, width - len(label_part) - 2)
    return f"┌{label_part}{fill}┐"


def box_sep(width: int) -> str:
    """Middle separator: ├──...──┤"""
    return f"├{'─' * (width - 2)}┤"


def box_bottom(width: int) -> str:
    """Bottom edge: └──...──┘"""
    return f"└{'─' * (width - 2)}┘"


def box_row(content: str, width: int) -> str:
    """Content row padded to width: │content   │"""
    pad = max(0, width - 2 - _visible_len(content))
    return f"│{content}{' ' * pad}│"


# ── Table drawing ─────────────────────────────────────────────────────────────

def tbl_top(col_widths: list[int]) -> str:
    return "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"


def tbl_sep(col_widths: list[int]) -> str:
    return "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"


def tbl_bottom(col_widths: list[int]) -> str:
    return "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"


def tbl_row(cells: list[str], col_widths: list[int]) -> str:
    parts = []
    for cell, w in zip(cells, col_widths):
        pad = " " * max(0, w - _visible_len(cell))
        parts.append(f" {cell}{pad} ")
    return "│" + "│".join(parts) + "│"


def wrap_text(text: str, width: int) -> list[str]:
    """Word-wrap text to width. For URLs, breaks at / or ? boundaries."""
    if len(text) <= width:
        return [text]
    is_url = text.startswith(("http://", "https://"))
    lines = []
    while text:
        if len(text) <= width:
            lines.append(text)
            break
        # Prefer breaking at word/URL boundaries
        if is_url:
            cut = max(
                text.rfind("/", 1, width),
                text.rfind("?", 1, width),
                text.rfind("&", 1, width),
            )
        else:
            cut = text.rfind(" ", 0, width)
        if cut <= 0:
            cut = width
        lines.append(text[:cut])
        text = text[cut:].lstrip("/") if is_url else text[cut:].lstrip()
    return lines
