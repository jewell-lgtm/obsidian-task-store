"""Check that a real vault survives being parsed and re-rendered.

Reads every task in a vault, renders it back, and compares to the original
line. Nothing is written — a clean run means it is safe to point the mutating
commands at that vault.

    python -m obsidian_task_store._roundtrip ~/vault
"""

from __future__ import annotations

import pathlib
import sys

from .config import Config
from .parse import iter_markdown, parse_document


def check(root):
    """Task sources only.

    Excluded files are not written by the mutating commands, so a checkbox in
    one failing to re-render is not a reason to keep them away from the vault.
    """
    config = Config.load(pathlib.Path(root).expanduser().resolve())
    root = config.root
    mismatches = []
    seen = 0
    for path in iter_markdown(root, config.is_excluded):
        lines = path.read_text().splitlines()
        for task in parse_document(path.read_text(), path=path):
            seen += 1
            original = lines[task.lineno - 1]
            if task.render() != original:
                mismatches.append((path.relative_to(root), task.lineno, original, task.render()))
    return seen, mismatches


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[0] if argv else "."
    seen, mismatches = check(root)
    for rel, lineno, original, rendered in mismatches:
        print(f"{rel}:{lineno}\n  was: {original!r}\n  got: {rendered!r}")
    if mismatches:
        print(f"\n{len(mismatches)} of {seen} tasks did not round-trip")
        return 1
    print(f"{seen} tasks round-tripped exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
