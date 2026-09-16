"""Checkboxes in a note, as opposed to tasks in a task source.

Some notes are deliberately not task sources — a day's plan, a handover's
acceptance criteria, a generated queue — yet they carry ``- [ ]`` lines that
reference real tasks by id. Ticking one is a text edit, not a completion:
``ots done`` still owns the task. So this module knows nothing about the emoji
vocabulary, sections, or rendering, and it never re-renders a line. It swaps
the single marker character and leaves the file otherwise byte for byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import AmbiguousNoteLine, NoteLineNotFound
from .locking import locked_text
from .parse import FENCE_RE

#: The status vocabulary the queue mirrors: open, in progress, complete.
#: ``doing`` is the ``[/]`` that ``ots start`` writes on a task.
MARKS = {"todo": " ", "doing": "/", "done": "x"}

STATUS_BY_MARK = {mark: status for status, mark in MARKS.items()}

CHECKBOX_RE = re.compile(r"^[ \t]*- \[(?P<mark>[^\]])\]")


@dataclass
class NoteMark:
    """What one mark did. ``changed`` is false when the line already said it."""

    path: object
    lineno: int
    status: str
    line: str
    changed: bool


def line_spans(text):
    """``(start, end)`` for each line's body, line terminators excluded.

    Written out rather than using ``splitlines``, which also breaks on form
    feeds and the unicode separators — characters that are body text in a
    markdown note, not line ends.
    """
    spans = []
    start = i = 0
    while i < len(text):
        char = text[i]
        if char == "\n":
            spans.append((start, i))
            i += 1
        elif char == "\r":
            spans.append((start, i))
            i += 2 if text[i + 1:i + 2] == "\n" else 1
        else:
            i += 1
            continue
        start = i
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def references(body, ident):
    """Does this line name ``ident`` as a task id?

    The id has to be a whole backticked token, which is how the queue writes it.
    A looser match would be a hazard rather than a convenience: ids are four hex
    characters, so a bare word match would also hit dates and short shas.
    """
    return re.search(rf"`{re.escape(ident)}`", body) is not None


def find_line(text, ident):
    """The one checkbox line referencing ``ident``: ``(lineno, start, end)``.

    Raises rather than guessing. A queue with the same id on two lines is a
    generator bug, and picking one of them would hide it.

    Fenced code is skipped, as it is for tasks: a note explaining how its own
    boxes work is the likeliest place to find an example checkbox carrying a
    real id, and ticking the documentation would be the worst outcome here.
    """
    hits = []
    fenced = False
    for n, (start, end) in enumerate(line_spans(text), 1):
        line = text[start:end]
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if CHECKBOX_RE.match(line) and references(line, ident):
            hits.append((n, start, end))
    if not hits:
        raise NoteLineNotFound(f"no checkbox line references `{ident}`")
    if len(hits) > 1:
        lines = ", ".join(str(n) for n, _, _ in hits)
        raise AmbiguousNoteLine(f"`{ident}` is on lines {lines}; refusing to guess")
    return hits[0]


def mark_line(path, ident, status="done"):
    """Set the checkbox marker on the line referencing ``ident``.

    Read, edit and write happen under one lock, so a caller never handles the
    file and two callers never overwrite each other. The edit itself is a
    one-character splice, which is what keeps the rest of the line — and the
    rest of the document — identical.
    """
    if status not in MARKS:
        raise ValueError(f"unknown status: {status}")
    want = MARKS[status]

    with locked_text(path) as handle:
        text = handle.read()
        lineno, start, end = find_line(text, ident)
        at = start + text[start:end].index("[") + 1
        if text[at] == want:
            return NoteMark(path, lineno, status, text[start:end], changed=False)
        edited = text[:at] + want + text[at + 1:]
        handle.seek(0)
        handle.write(edited)
        handle.truncate()
        return NoteMark(path, lineno, status, edited[start:end], changed=True)
