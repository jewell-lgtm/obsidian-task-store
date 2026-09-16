"""Vault configuration: ``.tasks.toml`` discovery, with working defaults."""

from __future__ import annotations

import os
import pathlib
import tomllib
from dataclasses import dataclass, field

from .errors import TaskStoreError

CONFIG_NAME = ".tasks.toml"
ENV_VAR = "OBSIDIAN_TASK_STORE_VAULT"


@dataclass
class Config:
    """How one vault is laid out.

    Every field has a default that works on a vault with no config file at all:
    a single ``todo.md`` with an ``Inbox`` heading, and no groups.
    """

    root: pathlib.Path
    inbox_file: str = "todo.md"
    inbox_section: str = "Inbox"
    sections: list = field(default_factory=lambda: ["Now", "Later", "Done"])
    done_section: str = "Done"
    groups: dict = field(default_factory=dict)
    exclude: list = field(default_factory=list)

    @classmethod
    def load(cls, start=None):
        root = _find_root(start)
        path = root / CONFIG_NAME
        data = tomllib.loads(path.read_text()) if path.exists() else {}

        inbox = data.get("inbox", "todo.md#Inbox")
        inbox_file, _, inbox_section = inbox.partition("#")
        return cls(
            root=root,
            inbox_file=inbox_file or "todo.md",
            inbox_section=inbox_section or "Inbox",
            sections=list(data.get("sections", ["Now", "Later", "Done"])),
            done_section=data.get("done_section", "Done"),
            groups=dict(data.get("groups", {})),
            exclude=list(data.get("exclude", [])),
        )

    def is_excluded(self, relpath):
        """Is this file kept out of the task sources?

        An excluded file's checkboxes are for ticking, not tasks: the day's
        plan, a handover's acceptance criteria, the generated queue. An entry
        names one file or, with or without a trailing slash, a folder.
        """
        rel = _slashes(relpath).removeprefix("./")
        for entry in self.exclude:
            entry = _slashes(entry).removeprefix("./").rstrip("/")
            if entry and (rel == entry or rel.startswith(f"{entry}/")):
                return True
        return False

    def note_path(self, path):
        """Resolve a note path given on the command line, inside the vault."""
        target = pathlib.Path(path).expanduser()
        target = target if target.is_absolute() else self.root / target
        target = target.resolve()
        try:
            rel = target.relative_to(self.root)
        except ValueError:
            raise TaskStoreError(f"{path} is outside the vault") from None
        if not target.is_file():
            raise TaskStoreError(f"no such file: {rel}")
        return target, rel

    def group_for(self, relpath, tags=()):
        """Which group a task belongs to: by folder first, then by tag."""
        rel = _slashes(relpath)
        best = ""
        for name, prefix in self.groups.items():
            prefix = prefix.rstrip("/") + "/"
            if rel.startswith(prefix) and len(prefix) > len(self.groups.get(best, "")):
                best = name
        if best:
            return best
        for tag in tags:
            if tag in self.groups:
                return tag
        return ""

    def todo_file(self, group=None):
        if not group:
            return self.root / self.inbox_file
        if group not in self.groups:
            raise KeyError(f"unknown group: {group}")
        return self.root / self.groups[group].rstrip("/") / self.inbox_file

    def group_root(self, group):
        if group not in self.groups:
            raise KeyError(f"unknown group: {group}")
        return self.root / self.groups[group].rstrip("/")


def _slashes(path):
    return str(path).replace(os.sep, "/")


def _find_root(start=None):
    if start:
        return pathlib.Path(start).expanduser().resolve()
    env = os.environ.get(ENV_VAR)
    if env:
        return pathlib.Path(env).expanduser().resolve()

    here = pathlib.Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / CONFIG_NAME).exists():
            return candidate
    for candidate in (here, *here.parents):
        if (candidate / "todo.md").exists():
            return candidate
    return here
