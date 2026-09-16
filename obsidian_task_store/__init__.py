"""Treat an Obsidian vault as a task store.

    from obsidian_task_store import TaskStore

    store = TaskStore.open("~/vault")
    for task in store.tasks(group="work"):
        print(task.id, task.title, task.due)
"""

from .config import Config
from .errors import (
    AmbiguousNoteLine,
    AmbiguousTask,
    NoteLineNotFound,
    SectionNotFound,
    StaleTask,
    TaskNotFound,
    TaskStoreError,
)
from .model import Task
from .notes import NoteMark
from .parse import parse_document, parse_vault
from .serialise import normalise
from .store import TaskStore

__version__ = "0.1.0"

__all__ = [
    "Config", "Task", "TaskStore", "NoteMark",
    "TaskStoreError", "TaskNotFound", "AmbiguousTask", "SectionNotFound", "StaleTask",
    "NoteLineNotFound", "AmbiguousNoteLine",
    "parse_document", "parse_vault", "normalise",
]
