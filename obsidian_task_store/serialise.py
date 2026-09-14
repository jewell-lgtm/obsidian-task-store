"""Writing documents back: whitespace normalisation and line-level edits.

These are pure functions over document text. File IO lives in the store.
"""

from __future__ import annotations

from .errors import SectionNotFound, StaleTask
from .parse import HEADING_RE


def normalise(text):
    """One blank line around every heading, no runs of blank lines.

    Programmatic edits otherwise accumulate whitespace: each insert leaves a
    gap, each removal leaves the gap behind.
    """
    out = []
    prev_heading = False
    for line in text.splitlines():
        if not line.strip():
            if out and not out[-1].strip():
                continue
            out.append("")
            prev_heading = False
            continue
        is_heading = bool(HEADING_RE.match(line))
        if is_heading and out and out[-1].strip():
            out.append("")
        elif prev_heading:
            out.append("")
        out.append(line.rstrip())
        prev_heading = is_heading
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n" if out else ""


def find_section(lines, title):
    for i, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading and heading.group(2).strip() == title:
            return i
    raise SectionNotFound(title)


def insert_into_section(text, title, line, *, end=False):
    """Insert ``line`` under the heading ``title``.

    Inserts at the top of the section by default: newest first, and it keeps the
    insert away from whatever the section's last line happens to be.
    """
    lines = text.splitlines()
    start = find_section(lines, title)

    if end:
        stop = len(lines)
        for i in range(start + 1, len(lines)):
            if HEADING_RE.match(lines[i]):
                stop = i
                break
        while stop > start + 1 and not lines[stop - 1].strip():
            stop -= 1
        at = stop
    else:
        at = start + 1
        while at < len(lines) and not lines[at].strip():
            at += 1

    return normalise("\n".join(lines[:at] + [line] + lines[at:]))


def replace_line(text, lineno, expect, replacement):
    """Swap one line, refusing if it is not what was read.

    ``replacement`` of None removes the line.
    """
    lines = text.splitlines()
    index = lineno - 1
    if index < 0 or index >= len(lines) or lines[index].strip() != expect.strip():
        found = lines[index] if 0 <= index < len(lines) else "<end of file>"
        raise StaleTask(f"line {lineno} is now {found!r}, expected {expect!r}")
    new = lines[:index] + ([replacement] if replacement is not None else []) + lines[index + 1:]
    return normalise("\n".join(new))


def remove_line(text, lineno, expect):
    return replace_line(text, lineno, expect, None)
