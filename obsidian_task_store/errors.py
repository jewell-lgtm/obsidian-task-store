"""Exceptions raised by the store."""


class TaskStoreError(Exception):
    """Base for everything this package raises."""


class TaskNotFound(TaskStoreError):
    pass


class AmbiguousTask(TaskStoreError):
    """More than one task answers to the same id."""


class SectionNotFound(TaskStoreError):
    pass


class StaleTask(TaskStoreError):
    """The line moved or changed since it was read.

    Guards the common case of another writer editing the vault between a read
    and a write. It is an optimistic check, not a lock.
    """


class NoteLineNotFound(TaskStoreError):
    """No checkbox line in the note references that task id."""


class AmbiguousNoteLine(TaskStoreError):
    """More than one checkbox line in the note references the same task id."""
