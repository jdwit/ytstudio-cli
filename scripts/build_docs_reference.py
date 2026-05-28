"""mkdocs hook: regenerate docs/reference.md from the live typer app.

Runs on every build so the command reference cannot drift from --help. We do
not check the generated file into git; instead it is produced under the
configured docs directory just before mkdocs walks the site.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def on_pre_build(config) -> None:
    docs_dir = Path(config["docs_dir"])
    reference = docs_dir / "reference.md"

    # typer ships its own CLI; using `python -m typer` avoids depending on a
    # console-script being on PATH inside the docs build environment.
    cmd = [
        sys.executable,
        "-m",
        "typer",
        "ytstudio.main",
        "utils",
        "docs",
        "--name",
        "ytstudio",
        "--output",
        str(reference),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # Fall back to a placeholder rather than failing the whole build; the
        # CI log shows the captured stderr so we can fix the root cause.
        sys.stderr.write("[build_reference] typer docs generation failed:\n")
        sys.stderr.write(result.stderr)
        reference.write_text(
            "# Command reference\n\n"
            "The auto-generated command reference could not be built. "
            "Run `python -m typer ytstudio.main utils docs --name ytstudio` "
            "locally to inspect the failure.\n"
        )
        return

    # Lift the top-level heading so it matches the nav label.
    text = reference.read_text()
    if text.lstrip().startswith("# `ytstudio`"):
        text = text.replace("# `ytstudio`", "# Command reference", 1)
        reference.write_text(text)
