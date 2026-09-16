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

try:
    import fcntl
except ImportError:  # Windows: no fcntl, so the cycle is unordered but intact.
    fcntl = None


@contextlib.contextmanager
def locked_text(path):
    """Yield a handle on ``path``, exclusively locked until the block ends.

    Opened with newline translation off, so whatever the file's line endings
    are, they survive being read and written back.
    """
    with open(path, "r+", encoding="utf-8", newline="") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            handle.flush()
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
