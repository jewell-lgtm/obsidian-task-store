"""An exclusive advisory lock held across a read-modify-write.

Task writes get away with an optimistic check: the caller names a task by id,
the store rewrites that one line, and a mismatch is refused as ``StaleTask``.
A note is different — the caller cannot name a line, so the whole file is read,
edited and written back, and two writers that interleave there lose an edit
silently rather than noisily. Holding the lock for the whole cycle makes the
second writer wait and re-read instead.

The lock is advisory and local to one machine: it orders writers that go
through this package, which is what races here, and not an editor saving over
the top.
"""

from __future__ import annotations

import contextlib

from .errors import TaskStoreError

try:
    import fcntl
except ImportError:  # No POSIX locks here — Windows, most likely.
    fcntl = None


@contextlib.contextmanager
def locked_text(path):
    """Yield a handle on ``path``, exclusively locked until the block ends.

    Opened with newline translation off, so whatever the file's line endings
    are, they survive being read and written back.

    Without a lock to take, the write is refused rather than done unguarded.
    The caller is told it has exclusive access for the cycle; doing the write
    anyway would make that a lie on exactly the platform where nobody looks.
    """
    if fcntl is None:
        raise TaskStoreError(
            "no file locking on this platform, so a note cannot be written safely"
        )
    with open(path, "r+", encoding="utf-8", newline="") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            handle.flush()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
