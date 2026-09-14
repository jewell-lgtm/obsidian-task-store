import pytest

from obsidian_task_store.model import Task

CORPUS = [
    "- [ ] Plain task",
    "- [x] Finished task ✅ 2026-09-14",
    "- [ ] Due task \U0001f4c5 2026-09-19",
    "- [ ] Every date ➕ 2026-09-01 \U0001f6eb 2026-09-02 ⏳ 2026-09-03 \U0001f4c5 2026-09-04",
    "- [-] Cancelled ❌ 2026-09-05",
    "- [ ] High priority ⏫",
    "- [ ] Highest priority \U0001f53a \U0001f4c5 2026-09-19",
    "- [ ] Lowest priority ⏬",
    "- [ ] Recurring \U0001f501 every week when done \U0001f4c5 2026-09-19",
    "- [ ] Has id \U0001f194 abc123",
    "- [ ] Blocked ⛔ abc123,def456",
    "- [ ] On completion \U0001f3c1 delete",
    "- [ ] Tagged #work #urgent \U0001f4c5 2026-09-19",
    "    - [ ] Indented subtask \U0001f4c5 2026-09-19",
    "- [ ] Everything \U0001f53a \U0001f501 every day ➕ 2026-09-01 \U0001f6eb 2026-09-02 "
    "⏳ 2026-09-03 \U0001f4c5 2026-09-04 ✅ 2026-09-05 \U0001f194 xyz ⛔ a,b \U0001f3c1 keep",
]


@pytest.mark.parametrize("line", CORPUS)
def test_round_trip_is_byte_identical(line):
    """An untouched task renders back exactly as it was read.

    This is what makes it safe to point the tool at a vault whose syntax it only
    partly understands.
    """
    task = Task.parse(line)
    assert task is not None
    assert task.render() == line


def test_parses_every_date_field():
    task = Task.parse(CORPUS[3])
    assert task.get("created") == "2026-09-01"
    assert task.get("start") == "2026-09-02"
    assert task.get("scheduled") == "2026-09-03"
    assert task.get("due") == "2026-09-04"
    assert task.description == "Every date"


def test_parses_priorities():
    assert Task.parse("- [ ] x \U0001f53a").priority == "highest"
    assert Task.parse("- [ ] x ⏫").priority == "high"
    assert Task.parse("- [ ] x \U0001f53c").priority == "medium"
    assert Task.parse("- [ ] x \U0001f53d").priority == "low"
    assert Task.parse("- [ ] x ⏬").priority == "lowest"
    assert Task.parse("- [ ] x").priority == "normal"


def test_recurrence_keeps_free_text():
    task = Task.parse(CORPUS[8])
    assert task.get("recurrence") == "every week when done"
    assert task.get("due") == "2026-09-19"


def test_blocked_by_keeps_the_whole_list():
    assert Task.parse(CORPUS[10]).get("blocked_by") == "abc123,def456"


def test_explicit_id_wins_over_the_derived_one():
    """A plugin id is what blocked_by points at, so it must be authoritative."""
    assert Task.parse("- [ ] Has id \U0001f194 abc123").id == "abc123"
    derived = Task.parse("- [ ] Has id").id
    assert len(derived) == 4 and derived != "abc123"


def test_derived_id_ignores_tags_and_dates():
    """Ids must survive the metadata changing, or they are not handles at all."""
    a = Task.parse("- [ ] Write the report #work \U0001f4c5 2026-09-19", group="work")
    b = Task.parse("- [ ] Write the report \U0001f4c5 2026-12-01 ⏫", group="work")
    assert a.id == b.id


def test_derived_id_differs_between_groups():
    a = Task.parse("- [ ] Same text", group="work")
    b = Task.parse("- [ ] Same text", group="home")
    assert a.id != b.id


def test_status_characters_other_than_x_are_preserved():
    task = Task.parse("- [-] Cancelled")
    assert task.status == "-"
    assert task.done is False
    assert task.render() == "- [-] Cancelled"


def test_canonical_render_orders_fields_like_the_plugin():
    task = Task.parse("- [ ] Thing \U0001f4c5 2026-09-19 ⏫")
    task.set("start", "2026-09-01")
    assert task.render() == (
        "- [ ] Thing ⏫ \U0001f6eb 2026-09-01 \U0001f4c5 2026-09-19"
    )


def test_non_task_lines_are_not_tasks():
    for line in ("# Heading", "Some prose", "- a bullet", "-[ ] no space", ""):
        assert Task.parse(line) is None


def test_title_strips_tags_but_description_keeps_them():
    task = Task.parse(CORPUS[12])
    assert task.description == "Tagged #work #urgent"
    assert task.title == "Tagged"
    assert task.tags == ["work", "urgent"]
