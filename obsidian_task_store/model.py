"""The Obsidian Tasks emoji vocabulary, and the Task record itself."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

DATE_SIGNIFIERS = {
    "created": "➕",
    "start": "\U0001f6eb",
    "scheduled": "⏳",
    "due": "\U0001f4c5",
    "cancelled": "❌",
    "done": "✅",
}

RECURRENCE = "\U0001f501"
ON_COMPLETION = "\U0001f3c1"
IDENTIFIER = "\U0001f194"
BLOCKED_BY = "⛔"

VALUE_SIGNIFIERS = {emoji: name for name, emoji in DATE_SIGNIFIERS.items()}
VALUE_SIGNIFIERS.update({
    RECURRENCE: "recurrence",
    ON_COMPLETION: "on_completion",
    IDENTIFIER: "identifier",
    BLOCKED_BY: "blocked_by",
})

PRIORITY_BY_EMOJI = {
    "\U0001f53a": "highest",
    "⏫": "high",
    "\U0001f53c": "medium",
    "\U0001f53d": "low",
    "⏬": "lowest",
}
EMOJI_BY_PRIORITY = {name: emoji for emoji, name in PRIORITY_BY_EMOJI.items()}

#: Rank for sorting; "normal" is the absence of a priority emoji.
PRIORITY_RANK = {"highest": 0, "high": 1, "medium": 2, "normal": 3, "low": 4, "lowest": 5}

#: The order fields are written in when a task is re-rendered. Only applies to
#: tasks whose fields actually changed — an untouched task keeps its own text.
RENDER_ORDER = (
    "priority", "recurrence", "created", "start", "scheduled", "due",
    "cancelled", "done", "identifier", "blocked_by", "on_completion",
)

DATE_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ALL = list(VALUE_SIGNIFIERS) + list(PRIORITY_BY_EMOJI)
SIGNIFIER_RE = re.compile("([" + "".join(_ALL) + "])")

TASK_RE = re.compile(r"^(?P<indent>[ \t]*)- \[(?P<mark>.)\] (?P<body>.*)$")


def split_body(body):
    """Split a task body into (description, [(signifier, value), ...]).

    Values run to the next signifier, which is what lets free-text fields like
    recurrence ("every week when done") and comma-separated blocked_by lists
    survive without needing a grammar per field.
    """
    parts = SIGNIFIER_RE.split(body)
    description = parts[0].strip()
    found = []
    for i in range(1, len(parts), 2):
        found.append((parts[i], parts[i + 1].strip()))
    return description, found


@dataclass
class Task:
    """One checkbox line.

    ``raw`` is the body exactly as it appeared. Rendering returns it verbatim
    unless a field was changed, so parsing and re-writing somebody else's vault
    is lossless even where this understands less of the line than they do.
    """

    description: str = ""
    done: bool = False
    status: str = " "
    priority: str = "normal"
    fields: dict = field(default_factory=dict)
    trailing: str = ""

    indent: str = ""
    raw: str = ""
    path: object = None
    lineno: int = 0
    section: str = ""
    group: str = ""

    _dirty: bool = False

    # ---------------------------------------------------------------- parsing

    @classmethod
    def parse(cls, line, *, path=None, lineno=0, section="", group=""):
        m = TASK_RE.match(line)
        if not m:
            return None
        body = m.group("body").rstrip()
        description, found = split_body(body)

        priority = "normal"
        fields = {}
        for emoji, value in found:
            if emoji in PRIORITY_BY_EMOJI:
                priority = PRIORITY_BY_EMOJI[emoji]
                # A priority mark carries no value; anything after it before the
                # next signifier belongs to the description.
                if value:
                    description = f"{description} {value}".strip()
                continue
            name = VALUE_SIGNIFIERS[emoji]
            fields[name] = value

        mark = m.group("mark")
        return cls(
            description=description,
            done=mark.lower() == "x",
            status=mark,
            priority=priority,
            fields=fields,
            indent=m.group("indent"),
            raw=body,
            path=path,
            lineno=lineno,
            section=section,
            group=group,
        )

    # ---------------------------------------------------------------- fields

    def get(self, name):
        return self.fields.get(name)

    def set(self, name, value):
        if value is None:
            self.fields.pop(name, None)
        else:
            self.fields[name] = value
        self._dirty = True

    def set_priority(self, priority):
        if priority not in PRIORITY_RANK:
            raise ValueError(f"unknown priority: {priority}")
        self.priority = priority
        self._dirty = True

    def set_description(self, description):
        self.description = description
        self._dirty = True

    def set_done(self, done, *, on=None):
        self.done = done
        self.status = "x" if done else " "
        if done and on:
            self.fields["done"] = on
        elif not done:
            self.fields.pop("done", None)
        self._dirty = True

    @property
    def due(self):
        return self.fields.get("due")

    @property
    def tags(self):
        return re.findall(r"#([A-Za-z0-9_\-/]+)", self.description)

    @property
    def title(self):
        """The description with tags stripped, for display."""
        s = re.sub(r"#[A-Za-z0-9_\-/]+", "", self.description)
        return re.sub(r"\s{2,}", " ", s).strip()

    @property
    def id(self):
        """A stable handle for this task.

        A plugin ``id`` field is authoritative when present — it is what
        ``blocked_by`` chains point at, so it must never be replaced. Otherwise
        derive one from group and title, which survives the task moving between
        files and sections.
        """
        explicit = self.fields.get("identifier")
        if explicit:
            return explicit
        return hashlib.sha1(f"{self.group}:{self.title}".encode()).hexdigest()[:4]

    # ---------------------------------------------------------------- render

    def render_body(self):
        if not self._dirty:
            return self.raw
        out = [self.description]
        for name in RENDER_ORDER:
            if name == "priority":
                if self.priority != "normal":
                    out.append(EMOJI_BY_PRIORITY[self.priority])
                continue
            value = self.fields.get(name)
            if value is None:
                continue
            emoji = DATE_SIGNIFIERS.get(name) or {
                "recurrence": RECURRENCE, "on_completion": ON_COMPLETION,
                "identifier": IDENTIFIER, "blocked_by": BLOCKED_BY,
            }[name]
            out.append(f"{emoji} {value}" if value else emoji)
        return " ".join(p for p in out if p).strip()

    def render(self):
        return f"{self.indent}- [{self.status}] {self.render_body()}"

    def as_dict(self):
        return {
            "id": self.id,
            "group": self.group,
            "title": self.title,
            "description": self.description,
            "done": self.done,
            "priority": self.priority,
            "tags": self.tags,
            "file": str(self.path) if self.path else None,
            "line": self.lineno,
            "section": self.section,
            **{k: v for k, v in sorted(self.fields.items())},
        }
