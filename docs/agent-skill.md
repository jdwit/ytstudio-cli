# Agent skill

This repo includes a model- and harness-agnostic **agent skill** so any
skill-aware AI agent can operate a YouTube channel through the CLI. It follows
the open [SKILL standard](https://agentskills.io): a folder with a `SKILL.md`
(YAML frontmatter plus instructions) and optional bundled resources.

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

The skill itself is vendor-neutral: every instruction is a shell command, with
no MCP server and nothing tied to a specific agent platform. It stresses the
rules that matter most when an agent drives the CLI: pass `-o json` for
parseable output, preview mutations that support `--execute`, and explicitly
confirm before immediate writes such as comment moderation/replies and
livestream start/stop.
