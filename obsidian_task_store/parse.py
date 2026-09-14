"""Scanning markdown documents and vaults into Task records."""

from __future__ import annotations

import re

from .model import Task

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_document(text, *, path=None, group=""):
    """Tasks in one document, with the heading each sits under.

    Fenced code blocks are skipped. Documentation and query blocks routinely
    contain example checkboxes, and reporting those as real tasks is worse than
    missing a task inside a fence.
    """
    tasks = []
    section = ""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            section = heading.group(2).strip()
            continue
        task = Task.parse(line, path=path, lineno=lineno, section=section, group=group)
        if task:
            tasks.append(task)
    return tasks


def iter_markdown(root):
    for path in sorted(root.rglob("*.md")):
        if any(part == ".git" or part.startswith(".") and part != "." for part in path.parts):
            continue
        yield path


def parse_vault(config):
    """Every task in the vault, with groups resolved from config."""
    tasks = []
    for path in iter_markdown(config.root):
        rel = path.relative_to(config.root)
        text = path.read_text()
        # Group by folder first; a tag can only settle it for files that sit
        # outside every group folder, such as the shared inbox.
        found = parse_document(text, path=path, group=config.group_for(rel))
        for task in found:
            if not task.group:
                task.group = config.group_for(rel, task.tags)
        tasks.extend(found)
    return tasks
