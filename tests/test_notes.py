"""Ticking one checkbox in a note that is not a task source."""

import pathlib
import subprocess
import sys
import threading

import pytest

from obsidian_task_store import Config, TaskStore
from obsidian_task_store.cli import main
from obsidian_task_store.errors import (
    AmbiguousNoteLine,
    NoteLineNotFound,
    TaskStoreError,
)
from obsidian_task_store.locking import locked_text

CONFIG = """
inbox = "todo.md#Inbox"
exclude = ["pima/queue.md", "pima/notes/handovers/", "daily/"]

[groups]
pima = "pima/"
"""

ITEM_0169 = (
    "- [/] **1 ·** **`0169` · PMO-463 — offline-sync queue hammering a 404.**"
    " · host: laptop · [[notes/handovers/risk-instances-terminal-404]]"
)
ITEM_6670 = (
    "- [ ] **6 ·** **`6670` · #861 — superseded on `main`; close it.**"
    " `41a4e28f` carries the fix. · **next:** close #861"
    " · [[notes/handovers/sentry-upload-ci-only]]"
)
ITEM_C2EC = (
    "- [x] **7 ·** **`c2ec` · #863 — the skill and the QA path fix.**"
    " · piece `prod-smoke-skill`"
)

QUEUE = f"""---
tags: [queue]
---

# PIMA queue — 2026-09-16

Ordered view over `ots` task ids. `[/]` means somebody is in that item's piece.

{ITEM_0169}
{ITEM_6670}
{ITEM_C2EC}
"""

TASK_FILE = """# PIMA

## Now

- [ ] Ship the thing `6670`

## Done
"""


@pytest.fixture
def queue_vault(vault):
    return vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "pima/queue.md": QUEUE, "pima/todo.md": TASK_FILE},
        config=CONFIG,
    )


def read(root, name="pima/queue.md"):
    return (root / name).read_bytes()


def line_of(text, ident):
    return next(line for line in text.splitlines() if f"`{ident}`" in line)


# ------------------------------------------------------------ the edit itself


def test_marks_only_the_referenced_line(queue_vault):
    before = read(queue_vault).decode()
    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    after = read(queue_vault).decode()

    pairs = zip(before.splitlines(), after.splitlines(), strict=True)
    changed = [(b, a) for b, a in pairs if b != a]
    assert len(changed) == 1
    was, now = changed[0]
    assert was.replace("- [ ]", "- [x]", 1) == now


def test_the_rest_of_the_line_survives_byte_for_byte(queue_vault):
    before = line_of(read(queue_vault).decode(), "6670")
    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    after = line_of(read(queue_vault).decode(), "6670")

    assert before[:3] == after[:3] == "- ["
    assert before[4:] == after[4:]
    assert (before[3], after[3]) == (" ", "x")
    assert after.endswith("· [[notes/handovers/sentry-upload-ci-only]]")


def test_one_character_differs_in_the_whole_file(queue_vault):
    before = read(queue_vault)
    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    after = read(queue_vault)

    assert len(before) == len(after)
    assert sum(1 for b, a in zip(before, after, strict=True) if b != a) == 1


def test_the_reported_line_number_is_the_line_that_moved(queue_vault):
    mark = TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    lines = read(queue_vault).decode().splitlines()
    assert "`6670`" in lines[mark.lineno - 1]
    assert mark.changed is True


# -------------------------------------------------------- the whole vocabulary


@pytest.mark.parametrize(
    "status,marker", [("todo", "- [ ]"), ("doing", "- [/]"), ("done", "- [x]")]
)
def test_every_status_in_the_vocabulary(queue_vault, status, marker):
    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md", status=status)
    assert line_of(read(queue_vault).decode(), "6670").startswith(marker)


def test_a_marked_line_can_be_taken_back_to_todo(queue_vault):
    store = TaskStore.open(queue_vault)
    store.mark_note("c2ec", "pima/queue.md", status="todo")
    assert line_of(read(queue_vault).decode(), "c2ec").startswith("- [ ]")


def test_an_unknown_status_is_refused(queue_vault):
    with pytest.raises(ValueError):
        TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md", status="binned")


# ----------------------------------------------------------------- idempotence


def test_marking_a_marked_line_does_not_rewrite_the_file(queue_vault):
    store = TaskStore.open(queue_vault)
    store.mark_note("6670", "pima/queue.md")
    stamp = (queue_vault / "pima/queue.md").stat().st_mtime_ns
    before = read(queue_vault)

    mark = store.mark_note("6670", "pima/queue.md")

    assert mark.changed is False
    assert read(queue_vault) == before
    assert (queue_vault / "pima/queue.md").stat().st_mtime_ns == stamp


# ---------------------------------------------------------------- loud failure


def test_an_id_on_no_line_changes_nothing(queue_vault):
    before = read(queue_vault)
    with pytest.raises(NoteLineNotFound, match="dead"):
        TaskStore.open(queue_vault).mark_note("dead", "pima/queue.md")
    assert read(queue_vault) == before


def test_an_id_on_two_lines_changes_nothing(queue_vault):
    path = queue_vault / "pima/queue.md"
    path.write_text(path.read_text() + "- [ ] **8 ·** a second line about `6670`\n")
    before = read(queue_vault)

    with pytest.raises(AmbiguousNoteLine, match="lines 10, 12"):
        TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    assert read(queue_vault) == before


def test_prose_that_names_the_id_is_not_a_checkbox_line(queue_vault):
    path = queue_vault / "pima/queue.md"
    path.write_text(path.read_text() + "\nItem `6670` is the one to close.\n")
    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    assert read(queue_vault).decode().endswith("Item `6670` is the one to close.\n")


def test_an_unbackticked_id_is_not_a_reference(vault):
    """Ids are four hex characters, so a bare match would also hit dates."""
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/2026-09-16.md": "- [ ] Planned 2026 review\n"},
        config='exclude = ["daily/"]\n',
    )
    with pytest.raises(NoteLineNotFound):
        TaskStore.open(root).mark_note("2026", "daily/2026-09-16.md")


def test_a_note_outside_the_vault_is_refused(queue_vault, tmp_path_factory):
    stray = tmp_path_factory.mktemp("elsewhere") / "queue.md"
    stray.write_text("- [ ] `6670` elsewhere\n")
    with pytest.raises(TaskStoreError, match="outside the vault"):
        TaskStore.open(queue_vault).mark_note("6670", str(stray))


def test_a_missing_note_is_refused(queue_vault):
    with pytest.raises(TaskStoreError, match="no such file"):
        TaskStore.open(queue_vault).mark_note("6670", "pima/nope.md")


# ------------------------------------------------------ never near a task file


def test_the_inbox_cannot_be_excluded_out_from_under_add(vault):
    """An excluded destination is refused before anything is written."""
    root = vault({"todo.md": "# Todo\n\n## Inbox\n"}, config='exclude = ["todo.md"]\n')
    before = (root / "todo.md").read_bytes()
    with pytest.raises(TaskStoreError, match="cannot hold tasks"):
        TaskStore.open(root).add("Buy milk")
    assert (root / "todo.md").read_bytes() == before


def test_a_link_into_an_excluded_folder_is_refused(queue_vault):
    """One file, one identity: an alias would be a note down one path only."""
    (queue_vault / "alias.md").symlink_to(queue_vault / "pima/queue.md")
    before = read(queue_vault)
    with pytest.raises(TaskStoreError, match="is a link to"):
        TaskStore.open(queue_vault).mark_note("6670", "alias.md")
    assert read(queue_vault) == before


def test_a_link_out_of_an_excluded_folder_is_refused(queue_vault):
    (queue_vault / "pima/notes/handovers").mkdir(parents=True)
    link = queue_vault / "pima/notes/handovers/sneaky.md"
    link.symlink_to(queue_vault / "pima/todo.md")
    before = read(queue_vault, "pima/todo.md")
    with pytest.raises(TaskStoreError, match="is a link to"):
        TaskStore.open(queue_vault).mark_note("6670", "pima/notes/handovers/sneaky.md")
    assert read(queue_vault, "pima/todo.md") == before


def test_a_task_source_is_refused(queue_vault):
    """`done` owns task completion; this must not be a second way in."""
    before = read(queue_vault, "pima/todo.md")
    with pytest.raises(TaskStoreError, match="task source"):
        TaskStore.open(queue_vault).mark_note("6670", "pima/todo.md")
    assert read(queue_vault, "pima/todo.md") == before


def test_marking_the_queue_leaves_the_task_open(queue_vault):
    store = TaskStore.open(queue_vault)
    store.mark_note("6670", "pima/queue.md")
    assert [t.title for t in store.tasks()] == ["Ship the thing `6670`"]


def test_an_excluded_note_is_not_a_task_source(queue_vault):
    """Without this the queue's own lines would be listed as tasks."""
    titles = [t.title for t in TaskStore.open(queue_vault).tasks(status="all")]
    assert titles == ["Ship the thing `6670`"]


def test_fmt_leaves_an_excluded_note_alone(queue_vault):
    """Whitespace `fmt` would certainly rewrite, in a file it must not open."""
    untidy = "# Plan\n\n\n\n- [ ] do `6670`   \n\n\n"
    (queue_vault / "pima/queue.md").write_text(untidy)
    (queue_vault / "pima/todo.md").write_text("# PIMA\n## Now\n\n\n\n## Done\n")

    changed = TaskStore.open(queue_vault).normalise_all()

    assert (queue_vault / "pima/queue.md").read_text() == untidy
    assert [str(p) for p in changed] == ["pima/todo.md"]


# -------------------------------------------------- what is not a checkbox line


def test_a_checkbox_inside_a_fence_is_not_a_line(queue_vault):
    """The likeliest place for an example id is the note explaining itself."""
    path = queue_vault / "pima/queue.md"
    path.write_text(path.read_text() + "\n```\n- [ ] **6 ·** **`6670`** example\n```\n")
    before = read(queue_vault)

    TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")

    after = read(queue_vault).decode()
    assert after.endswith("```\n- [ ] **6 ·** **`6670`** example\n```\n")
    assert len(before) == len(after.encode())


def test_an_empty_note_has_no_line(vault):
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": ""},
        config='exclude = ["daily/"]\n',
    )
    with pytest.raises(NoteLineNotFound):
        TaskStore.open(root).mark_note("6670", "daily/plan.md")
    assert (root / "daily/plan.md").read_bytes() == b""


def test_a_note_that_is_only_frontmatter_has_no_line(vault):
    text = "---\ntags: [queue]\n---\n"
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": text},
        config='exclude = ["daily/"]\n',
    )
    with pytest.raises(NoteLineNotFound):
        TaskStore.open(root).mark_note("6670", "daily/plan.md")
    assert (root / "daily/plan.md").read_text() == text


# ------------------------------------------------------------- file mechanics


def test_crlf_endings_survive(vault):
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": "# Plan\r\n\r\n- [ ] do `6670`\r\n"},
        config='exclude = ["daily/"]\n',
    )
    TaskStore.open(root).mark_note("6670", "daily/plan.md")
    assert (root / "daily/plan.md").read_bytes() == b"# Plan\r\n\r\n- [x] do `6670`\r\n"


def test_a_missing_trailing_newline_stays_missing(vault):
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": "# Plan\n\n- [ ] do `6670`"},
        config='exclude = ["daily/"]\n',
    )
    TaskStore.open(root).mark_note("6670", "daily/plan.md")
    assert (root / "daily/plan.md").read_bytes() == b"# Plan\n\n- [x] do `6670`"


def test_blank_line_runs_and_indentation_survive(vault):
    text = "# Plan\n\n\n\n   - [ ] nested `6670`   \n\n\n"
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": text},
        config='exclude = ["daily/"]\n',
    )
    TaskStore.open(root).mark_note("6670", "daily/plan.md")
    assert (root / "daily/plan.md").read_text() == text.replace("- [ ]", "- [x]")


def test_mixed_endings_and_multibyte_prose_survive(vault):
    text = "# Plan é\r\n\n\t- [ ] ship 目標 `6670` — now\r\nlast line"
    root = vault(
        {"todo.md": "# Todo\n\n## Inbox\n", "daily/plan.md": text},
        config='exclude = ["daily/"]\n',
    )
    TaskStore.open(root).mark_note("6670", "daily/plan.md")
    marked = text.replace("- [ ]", "- [x]").encode()
    assert (root / "daily/plan.md").read_bytes() == marked


# ------------------------------------------------------------------ the lock


def test_another_process_waits_rather_than_clobbering(queue_vault):
    """The guarantee is between `ots` processes, so prove it between processes.

    The lock is held here while a real `ots` runs against the same note. It has
    to block: if it reads now, it reads text without the edit this test is
    about to make, and writing that back loses it. Then its own mark has to
    land on top of that edit rather than instead of it.
    """
    path = queue_vault / "pima/queue.md"
    argv = [sys.executable, "-m", "obsidian_task_store.cli", "--vault", str(queue_vault),
            "note", "mark", "6670", "--in", "pima/queue.md"]

    with locked_text(path) as handle:
        text = handle.read()
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            child.wait(0.5)
        except subprocess.TimeoutExpired:
            pass
        assert child.poll() is None, "the second writer did not wait for the lock"
        handle.seek(0)
        handle.write(text.replace("- [/] **1", "- [x] **1", 1))
        handle.truncate()

    assert child.wait(10) == 0

    final = path.read_text()
    assert line_of(final, "0169").startswith("- [x]"), "the held edit was clobbered"
    assert line_of(final, "6670").startswith("- [x]")


def test_concurrent_marks_do_not_lose_each_other(queue_vault, monkeypatch):
    """Two agents ticking two items: the second must re-read, not overwrite.

    The threads are interleaved at the point each has read the file: without a
    lock held across the whole read-modify-write, the second writer ships back
    a copy of the text it read before the first writer's edit, and that tick
    disappears with no error anywhere.
    """
    from obsidian_task_store import notes

    real_find = notes.find_line
    first_read = threading.Event()
    second_read = threading.Event()

    def interleave(text, ident):
        if ident == "6670":
            first_read.set()
            second_read.wait(0.3)
        else:
            first_read.wait(2)
            second_read.set()
        return real_find(text, ident)

    monkeypatch.setattr(notes, "find_line", interleave)
    store = TaskStore.open(queue_vault)

    threads = [
        threading.Thread(target=store.mark_note, args=(ident, "pima/queue.md"))
        for ident in ("6670", "0169")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()

    text = read(queue_vault).decode()
    assert line_of(text, "6670").startswith("- [x]")
    assert line_of(text, "0169").startswith("- [x]")


# ------------------------------------------------------------------- the cli


def test_cli_marks_the_line(queue_vault, capsys):
    assert main(["--vault", str(queue_vault), "note", "mark", "6670",
                 "--in", "pima/queue.md"]) == 0
    assert capsys.readouterr().out == "6670  done  pima/queue.md:10\n"
    assert line_of(read(queue_vault).decode(), "6670").startswith("- [x]")


def test_cli_says_when_there_was_nothing_to_do(queue_vault, capsys):
    argv = ["--vault", str(queue_vault), "note", "mark", "c2ec", "--in", "pima/queue.md"]
    assert main(argv) == 0
    assert capsys.readouterr().out == "c2ec  already done  pima/queue.md:11\n"


def test_cli_writes_the_doing_marker(queue_vault, capsys):
    argv = ["--vault", str(queue_vault), "note", "mark", "6670",
            "--in", "pima/queue.md", "--as", "doing"]
    assert main(argv) == 0
    assert capsys.readouterr().out == "6670  doing  pima/queue.md:10\n"
    assert line_of(read(queue_vault).decode(), "6670").startswith("- [/]")


def test_cli_reports_a_refusal_on_stderr(queue_vault, capsys):
    argv = ["--vault", str(queue_vault), "note", "mark", "6670", "--in", "pima/todo.md"]
    assert main(argv) == 1
    err = capsys.readouterr().err
    assert err.startswith("ots: pima/todo.md is a task source")


def test_cli_requires_the_file(queue_vault):
    with pytest.raises(SystemExit):
        main(["--vault", str(queue_vault), "note", "mark", "6670"])


# --------------------------------------------------------------- what excludes


@pytest.mark.parametrize(
    "entry,rel,excluded",
    [
        ("pima/queue.md", "pima/queue.md", True),
        ("pima/queue.md", "pima/queue.md.bak", False),
        ("pima/notes/handovers/", "pima/notes/handovers/pmo-169.md", True),
        ("pima/notes/handovers", "pima/notes/handovers/pmo-169.md", True),
        ("daily/", "daily/2026-09-16.md", True),
        ("daily/", "dailyplan.md", False),
        ("daily/", "pima/daily/2026-09-16.md", False),
    ],
)
def test_an_exclude_entry_names_a_file_or_a_folder(entry, rel, excluded):
    assert Config(root=pathlib.Path("/vault"), exclude=[entry]).is_excluded(rel) is excluded


def test_a_vault_with_no_exclude_excludes_nothing(grouped_vault):
    assert TaskStore.open(grouped_vault).config.exclude == []


def test_without_file_locking_the_write_is_refused(queue_vault, monkeypatch):
    """A platform with no lock gets a refusal, not an unguarded write."""
    from obsidian_task_store import locking

    monkeypatch.setattr(locking, "fcntl", None)
    before = read(queue_vault)
    with pytest.raises(TaskStoreError, match="no file locking"):
        TaskStore.open(queue_vault).mark_note("6670", "pima/queue.md")
    assert read(queue_vault) == before
