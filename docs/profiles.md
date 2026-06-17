# Multi-channel profiles

ytstudio stores each YouTube login under its own named profile, so one
install can drive multiple channels. Every command operates on the
**active** profile unless you override it for a single invocation.

## Commands

```bash
ytstudio profile add work       # authenticate a new channel and make it active
ytstudio profile add personal   # add another channel
ytstudio profile list           # show profiles; the active one is marked with *
ytstudio profile use work       # switch the active profile
ytstudio profile status work    # auth status for one profile (defaults to active)
ytstudio profile remove personal
```

## Per-command override

Useful in scripts: switch channel for one command without changing global
state.

```bash
YTSTUDIO_PROFILE=work ytstudio videos list
```

## Storage

```
~/.config/ytstudio-cli/
├── client_secrets.json         # shared OAuth client, written by init
├── state.json                  # active profile pointer (atomic writes)
└── profiles/
    ├── default/
    │   ├── credentials.json    # 0600
    │   └── meta.json
    └── work/
        ├── credentials.json
        └── meta.json
```

Profile directories are `0700`; credential files are `0600`. State writes go
through an atomic temp + rename and are serialized under an `fcntl` lock, so
concurrent CLI invocations cannot leave the file partially written.
