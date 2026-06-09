# MCP server mode

`ytstudio` ships an optional [Model Context Protocol](https://modelcontextprotocol.io)
server so AI agents (Claude Desktop, Cursor, custom clients) can manage your
YouTube channel through the same surface you use from the terminal.

## Install

The MCP server requires the `mcp` extra:

```bash
uv tool install "ytstudio-cli[mcp]"
```

You still need to authenticate with `ytstudio login` (the MCP server reuses
the same OAuth profile the CLI uses).

## Configure a client

Generate a ready-to-paste config block:

```bash
ytstudio mcp print-config --client claude-desktop
```

Example output:

```json
{
  "mcpServers": {
    "ytstudio": {
      "command": "/usr/local/bin/ytstudio",
      "args": ["mcp", "serve"]
    }
  }
}
```

Add `--allow-write` to embed `YTSTUDIO_MCP_ALLOW_WRITE=1` in the `env` block
so the agent can call write tools.

`--client` accepts `claude-desktop`, `cursor`, or `generic`.

## Run the server

```bash
ytstudio mcp serve                     # stdio (default), read-only
ytstudio mcp serve --allow-write       # stdio with write tools
ytstudio mcp serve --transport http    # HTTP on 127.0.0.1:8765
ytstudio mcp serve --read-only         # force read-only even if env is set
ytstudio mcp serve --profile work      # explicit profile (defaults to active)
```

`ytstudio mcp tools` prints the tool list without running the server, which is
useful while wiring up an agent.

## Environment variables

| Variable | Effect |
| --- | --- |
| `YTSTUDIO_MCP_ALLOW_WRITE=1` | Equivalent to `--allow-write`. `--read-only` and `--allow-write` both win over this. |
| `YTSTUDIO_PROFILE` | Selects the OAuth profile, same as elsewhere in the CLI. `--profile` wins. |

Precedence for write access: `--read-only` > `--allow-write` >
`YTSTUDIO_MCP_ALLOW_WRITE=1` > default off.

## Security model

- Stream keys are always redacted; no MCP tool returns the raw value, even in
  write mode.
- HTTP transport binds to `127.0.0.1` by default. Binding to `0.0.0.0` prints
  a warning because there is no transport-level authentication; only do this
  on a trusted network.
- Quota/permission errors are translated into MCP `ToolError`s so the server
  keeps running across failed calls instead of exiting.
- Auth/setup commands (`init`, `login`, `status`, `profile.*`) and video
  upload are intentionally not exposed; they stay terminal-only.

## Read tools (always on)

- `whoami` -- channel id, title, subscribers, video count
- `list_videos`, `get_video`, `list_categories`
- `analytics_overview`, `analytics_query` (same surface as
  `ytstudio analytics query`)
- `list_comments`
- `list_broadcasts`, `get_broadcast` (stream key always redacted)
- `list_playlists`, `get_playlist`, `list_playlist_items`
- `list_captions`

## Write tools (require `--allow-write` or env)

- `update_video`
- `publish_comments`, `reject_comments`
- `schedule_broadcast`, `transition_broadcast`, `update_broadcast`
- `create_playlist`, `update_playlist`, `delete_playlist`
- `add_to_playlist`, `remove_from_playlist`

`schedule_broadcast` requires `made_for_kids` to be passed explicitly; YouTube
mandates the COPPA self-declaration on every broadcast.

## Deferred follow-ups

- Caption writes (`captions().insert/update/delete`) are not exposed yet;
  only `list_captions` is available.
- Interactive comment moderation TUI lives in the CLI, not in MCP.
- There is no HTTP-level auth on `mcp serve --transport http`; treat it as
  loopback-only.
