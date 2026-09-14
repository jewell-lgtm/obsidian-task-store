"""Treat an Obsidian vault as a task store.

    from obsidian_task_store import TaskStore

    store = TaskStore.open("~/vault")
    for task in store.tasks(group="work"):
        print(task.id, task.title, task.due)
"""

from .config import Config
from .errors import (
    AmbiguousTask,
    SectionNotFound,
    StaleTask,
    TaskNotFound,
    TaskStoreError,
)
from .model import Task
from .parse import parse_document, parse_vault
from .serialise import normalise
from .store import TaskStore

__version__ = "0.1.0"

__all__ = [
    "Config", "Task", "TaskStore",
    "TaskStoreError", "TaskNotFound", "AmbiguousTask", "SectionNotFound", "StaleTask",
    "parse_document", "parse_vault", "normalise",
]
