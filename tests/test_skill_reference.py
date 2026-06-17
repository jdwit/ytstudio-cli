"""The skill's bundled command reference must track the CLI surface.

``skills/ytstudio/references/reference.md`` is checked into git (it ships with
the skill), so it can silently drift when commands or flags change. This test
re-renders it from the live typer app and fails if the committed copy is stale,
pointing at the regeneration command.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_skill_reference.py"
REFERENCE = REPO_ROOT / "skills" / "ytstudio" / "references" / "reference.md"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_skill_reference", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_reference_is_in_sync():
    builder = _load_builder()
    expected = builder.render()
    actual = REFERENCE.read_text()
    assert actual == expected, (
        "skills/ytstudio/references/reference.md is out of date.\n"
        "Regenerate it with: uv run python scripts/build_skill_reference.py"
    )
