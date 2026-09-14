# obsidian-task-store

Treat an Obsidian vault as a task store — read tasks, and **write them back without
wrecking the document**.

Plenty of tools read an Obsidian vault. Writing to one is the harder half: splice a line
into markdown and you leave blank lines behind, lose the fields you did not parse, and
have no stable way to refer to a task once it moves. This handles those three things.

Not on PyPI yet — install from the repo:

```bash
pip install git+https://github.com/jewell-lgtm/obsidian-task-store
```

```console
$ ots list --group work
0f98  [ ]  work  2026-09-16  Chase VPN access for the new starter
ec95  [ ]  work  2026-09-19  Write up Q3 capacity numbers
cf76  [ ]  work           —  Review the deployment runbook

3 tasks

$ ots add "Book the team retro" --group work --due 2026-09-22
a41c  added  Book the team retro

$ ots done 0f98
0f98  done  Chase VPN access for the new starter
```

## What it does that a regex does not

**Round-trips losslessly.** A task is rendered back exactly as it was read, byte for byte,
unless you deliberately changed a field. Fields this package does not understand survive
untouched, so it is safe to point at a vault whose conventions differ from yours.

**Stable task ids.** Every task has a short id derived from its group and title, so it
survives the task moving between files and sections — `ots done 0f98` works on the id you
saw in a listing ten minutes ago. A task carrying the Tasks plugin's own `🆔` keeps it, and
that id wins, because `⛔` dependency chains point at it.

**Documents stay tidy.** Every write re-normalises whitespace: one blank line around each
heading, no accumulating runs. Repeated programmatic edits do not degrade the file.

**Fenced code is not parsed.** Documentation and query blocks are full of example
checkboxes. Reporting those as real tasks is worse than missing them.

## The full emoji vocabulary

Parses the [Obsidian Tasks](https://publish.obsidian.md/tasks/) emoji format:

| Field | Signifier | Example |
| --- | --- | --- |
| Created | ➕ | `➕ 2026-09-01` |
| Start | 🛫 | `🛫 2026-09-02` |
| Scheduled | ⏳ | `⏳ 2026-09-03` |
| Due | 📅 | `📅 2026-09-04` |
| Cancelled | ❌ | `❌ 2026-09-05` |
| Done | ✅ | `✅ 2026-09-06` |
| Priority | 🔺 ⏫ 🔼 🔽 ⏬ | `⏫` |
| Recurrence | 🔁 | `🔁 every week when done` |
| On completion | 🏁 | `🏁 delete` |
| Id | 🆔 | `🆔 abc123` |
| Blocked by | ⛔ | `⛔ abc123,def456` |

## Configuration

Works with no configuration: a `todo.md` with an `## Inbox` heading is a valid vault.

To describe a vault split into groups, drop a `.tasks.toml` at its root:

```toml
inbox = "todo.md#Inbox"
sections = ["Now", "Later", "Done"]

[groups]
work = "work/"
home = "home/"
```

A task's group comes from the folder it lives in. For the shared inbox, which sits outside
every group folder, a `#work` tag settles it instead.

## Library

The CLI is a thin layer over the library:

```python
from obsidian_task_store import TaskStore

store = TaskStore.open("~/vault")

for task in store.tasks(group="work", due_before="2026-10-01"):
    print(task.id, task.title, task.due, task.priority)

task = store.add("Book the team retro", group="work", due="2026-09-22")
store.move(task.id, group="work", section="Now")
store.complete(task.id)
```

Parsing alone, without a vault:

```python
from obsidian_task_store import Task

task = Task.parse("- [ ] Ship it ⏫ 🔁 every week 📅 2026-09-19")
task.priority        # 'high'
task.due             # '2026-09-19'
task.get("recurrence")  # 'every week'
task.render()        # unchanged, byte for byte
```

## Built for agents

The default output is one line per task with no file paths, because the common caller is
an LLM paying for every token it reads. `--json` gives the full record when something
needs to process it, and `-v` adds `file:line` when a human is debugging.

## Concurrency

Writes are guarded: if the target line is not what was read, the write is refused with
`StaleTask` rather than clobbering somebody else's edit. This is an optimistic check, not
a lock — it catches a vault edited in Obsidian or by another process between your read and
your write, but two writers racing within the same moment can still interleave.

## Development

Uses [mise](https://mise.jdx.dev/):

```bash
mise install       # python + uv
mise run install   # dependencies
mise run test
mise run lint
```

Before pointing the mutating commands at a vault you care about, check it round-trips:

```bash
mise run roundtrip ~/vault
```

## Licence

MIT
