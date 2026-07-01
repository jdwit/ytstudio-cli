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

## Brand voice

Each profile can carry a **brand voice**: a markdown file describing the house
style an agent should follow when authoring video metadata. It is stored next
to the profile's credentials and fed verbatim into an agent's context by
[metadata authoring](videos.md#authoring-metadata).

```bash
ytstudio profile brand show                  # print the active profile's brand voice
ytstudio profile brand edit                  # create/open brand.md in $EDITOR
ytstudio profile brand set --file style.md   # import a brand file non-interactively
ytstudio profile brand show --profile work   # target a specific profile
```

`brand edit` seeds a template on first use and opens `$EDITOR`; `brand set`
imports an existing markdown file. All three accept `--profile/-p` to target a
profile other than the active one. `brand show` prints the raw markdown to
stdout so an agent can capture it into a system prompt, and exits non-zero when
no brand voice is set yet.

The file lives at `profiles/<name>/brand.md` and is written owner-only
(`0600`), the same as credentials, because a brand voice can encode private
channel strategy.

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
        ├── meta.json
        └── brand.md            # optional; per-channel brand voice (0600)
```

Profile directories are `0700`; credential files are `0600`. State writes go
through an atomic temp + rename and are serialized under an `fcntl` lock, so
concurrent CLI invocations cannot leave the file partially written.
