"""Exceptions raised by the store."""


class TaskStoreError(Exception):
    """Base for everything this package raises."""


class TaskNotFound(TaskStoreError):
    """No task carries this id.

    Ids are hashed from the title, so a reworded task gets a new id and every
    external reference to the old one goes stale. The message says so, because
    the caller is usually an agent holding an id it read minutes ago.
    """

    def __init__(self, ident):
        super().__init__(
            f"no task with id {ident!r} — ids change when a title is edited; "
            f"run `ots list` and take the current id"
        )
        self.ident = ident


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
