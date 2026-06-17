# Agent skill

ytstudio ships a model- and harness-agnostic **agent skill** so any skill-aware
AI agent can operate a YouTube channel through the CLI. It follows the open
[SKILL standard](https://agentskills.io): a folder with a `SKILL.md` (YAML
frontmatter plus instructions) and optional bundled resources.

The skill lives in this repository at
[`skills/ytstudio/`](https://github.com/jdwit/ytstudio-cli/tree/main/skills/ytstudio):

```
skills/ytstudio/
├── SKILL.md                          # frontmatter + instructions
├── references/
│   └── reference.md                  # full command reference (generated)
└── assets/
    └── upload-sidecar.example.yaml   # example upload sidecar
```

## Using it

A public GitHub repo containing a `SKILL.md` is already a published skill, so no
separate package or repo is needed. Point your agent runtime (or a registry such
as [skills.sh](https://skills.sh)) at the `skills/ytstudio/` subpath; monorepo
skills in a subfolder are supported by the spec.

The skill itself is vendor-neutral: every instruction is a shell command, with
no MCP server and nothing tied to a specific agent platform. It stresses the two
rules that matter most when an agent drives the CLI: pass `-o json` for parseable
output, and that mutating commands are dry-run by default until re-run with
`--execute`.

## Keeping the reference in sync

`skills/ytstudio/references/reference.md` is the full command reference. Unlike
the site's [command reference](reference.md) (built on the fly by mkdocs and
git-ignored), the skill copy is checked into git because it travels with the
skill when installed from the repo, so it can drift from the CLI.

Two things keep it honest, both driven from the same typer app as the rest of
the docs:

- Regenerate it after any change to the CLI surface:

    ```bash
    uv run python scripts/build_skill_reference.py
    ```

- CI guards against drift: `tests/test_skill_reference.py` re-renders the
    reference and fails if the committed copy is stale, pointing at the command
    above.
