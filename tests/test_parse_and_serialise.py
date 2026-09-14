import pytest

from obsidian_task_store.errors import SectionNotFound, StaleTask
from obsidian_task_store.parse import parse_document
from obsidian_task_store.serialise import (
    insert_into_section,
    normalise,
    remove_line,
    replace_line,
)

FENCED = """# Notes

- [ ] A real task

```markdown
- [ ] An example in a fence
```

~~~
- [ ] An example in a tilde fence
~~~

- [ ] Another real task
"""


def test_fenced_examples_are_not_tasks():
    """Docs and query blocks are full of example checkboxes."""
    tasks = parse_document(FENCED)
    assert [t.description for t in tasks] == ["A real task", "Another real task"]


def test_section_is_the_nearest_heading_above():
    tasks = parse_document("## Now\n\n- [ ] a\n\n## Later\n\n- [ ] b\n")
    assert [(t.description, t.section) for t in tasks] == [("a", "Now"), ("b", "Later")]


def test_line_numbers_count_every_line_including_fences():
    tasks = parse_document(FENCED)
    assert tasks[0].lineno == 3
    assert FENCED.splitlines()[tasks[1].lineno - 1] == "- [ ] Another real task"


TIDY = "# Title\n\nProse here.\n\n## Section\n\n- [ ] task\n"


def test_normalise_is_a_no_op_on_tidy_text():
    assert normalise(TIDY) == TIDY


def test_normalise_is_idempotent():
    messy = "# Title\n\n\n\nProse\n## Section\n- [ ] task\n\n\n"
    once = normalise(messy)
    assert normalise(once) == once


def test_normalise_collapses_runs_and_spaces_headings():
    assert normalise("# A\n\n\n\n## B\n- [ ] t\n") == "# A\n\n## B\n\n- [ ] t\n"


def test_insert_goes_to_the_top_of_the_section():
    text = "## Now\n\n- [ ] old\n\n## Later\n"
    out = insert_into_section(text, "Now", "- [ ] new")
    assert out.splitlines()[:4] == ["## Now", "", "- [ ] new", "- [ ] old"]


def test_insert_at_end_stays_inside_the_section():
    text = "## Now\n\n- [ ] old\n\n## Later\n"
    out = insert_into_section(text, "Now", "- [ ] new", end=True)
    lines = out.splitlines()
    assert lines.index("- [ ] new") < lines.index("## Later")
    assert lines.index("- [ ] old") < lines.index("- [ ] new")


def test_insert_into_missing_section_raises():
    with pytest.raises(SectionNotFound):
        insert_into_section("# A\n", "Nope", "- [ ] x")


def test_insert_leaves_no_whitespace_debris():
    """The bug that motivated the parser: repeated edits growing blank lines."""
    text = "## Now\n\n## Done\n"
    for i in range(5):
        text = insert_into_section(text, "Now", f"- [ ] task {i}")
    for i in range(5):
        text = remove_line(text, text.splitlines().index(f"- [ ] task {i}") + 1,
                           f"- [ ] task {i}")
    assert text == "## Now\n\n## Done\n"


def test_remove_refuses_when_the_line_changed():
    text = "## Now\n\n- [ ] mine\n"
    with pytest.raises(StaleTask):
        remove_line(text, 3, "- [ ] somebody else's")


def test_replace_refuses_past_the_end_of_file():
    with pytest.raises(StaleTask):
        replace_line("# A\n", 99, "- [ ] x", "- [x] x")
