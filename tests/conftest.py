import pytest


@pytest.fixture
def vault(tmp_path):
    """Build a throwaway vault from a {relative path: text} mapping."""

    def build(files, config=None):
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        if config is not None:
            (tmp_path / ".tasks.toml").write_text(config)
        return tmp_path

    return build


CONFIG = """
inbox = "todo.md#Inbox"
sections = ["Now", "Later", "Done"]

[groups]
work = "work/"
home = "home/"
"""

INBOX = """# Todo

## Inbox

## Open
"""

GROUP_FILE = """# {title}

## Now

## Later

## Done
"""


@pytest.fixture
def grouped_vault(vault):
    return vault(
        {
            "todo.md": INBOX,
            "work/todo.md": GROUP_FILE.format(title="Work"),
            "home/todo.md": GROUP_FILE.format(title="Home"),
        },
        config=CONFIG,
    )
