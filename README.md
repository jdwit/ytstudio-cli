<h1 align="center">YT Studio CLI</h1>

<p align="center">
  <img src="ascii.png" alt="ascii">
</p>

<p align="center">
  <a href="https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml"><img src="https://github.com/jdwit/ytstudio-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/jdwit/ytstudio-cli"><img src="https://codecov.io/gh/jdwit/ytstudio-cli/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://pypi.org/project/ytstudio-cli/"><img src="https://img.shields.io/pypi/v/ytstudio-cli" alt="PyPI"></a>
  <a href="https://pypi.org/project/ytstudio-cli/"><img src="https://img.shields.io/pypi/pyversions/ytstudio-cli" alt="Python"></a>
</p>

<p align="center">
  Manage and analyze your YouTube channel from the terminal. Designed for humans and AI agents.
</p>

> [!NOTE]
> This is **not** an official Google product, see [disclaimer](#disclaimer).

## Motivation

I built this because I needed to bulk update video titles for a YouTube channel I manage with 300+
videos. YouTube Studio does not support bulk search-replace operations, which made it a tedious
manual process. This tool uses the YouTube Data API to perform bulk operations on video metadata.
Furthermore, it provides features for analytics and comment moderation, all accessible from the
command line.

## Features

- Bulk update video metadata across hundreds of videos in one pass (search-replace titles,
  descriptions, tags).
- Upload videos from a directory using YAML sidecars for metadata and thumbnails.
- Schedule, start, stop, and update YouTube livestream broadcasts, including RTMP ingest details.
- Multi-channel profiles: manage several channels from one machine and switch per command.
- Comments moderation: list, reply, approve, reject, and ban from the CLI.
- Channel analytics queries via the YouTube Analytics API.
- Playlists: bulk-add by search and reorder by views with one command.
- [Agentic authoring](#agentic-authoring): edit descriptions and metadata with the help of an AI
  agent, grounded in the video's actual transcript and shaped by a per-channel brand voice.

## Documentation

See the [full documentation](https://jdwit.github.io/ytstudio-cli/) for installation, OAuth setup, and the command reference.

## Agentic authoring

Writing a good title or description is a creative, per-video task. Instead of adding an
"AI" command, this CLI gives an agent the raw materials to do it well and stay honest,
then applies the result through the ordinary update path:

- **Transcript grounding.** `videos captions <id>` lists a video's caption tracks and
  `videos transcript <id> [--lang nl]` pulls one as clean plain text (timestamps and
  SRT markup stripped), so the copy is based on what was actually said rather than a
  hallucination.
- **Per-channel brand voice.** `profile brand edit` (opens `$EDITOR`) or
  `profile brand set --file <path>` store a free-form `brand.md` next to each profile,
  holding the house style (audience, tone, title conventions) an agent should follow so
  output sounds on-brand instead of generic.
- **Apply it.** The agent drafts the metadata and applies it through the existing
  `videos update <id> --title ... --description ...` path (dry-run by default, then
  `--execute`).

The CLI itself never calls a model: it supplies the inputs and applies the change,
while a skill-aware AI agent (such as [Claude Code](https://claude.com/claude-code) or Pi)
writes the copy by running the [agent skill](skills/ytstudio/SKILL.md) below. The transcript is the source of truth for
claims and the brand file is the source of truth for tone, so the agent never states
anything the transcript does not support. There is no LLM or API key to configure here;
that lives with whichever agent you run.

## Agent skill

This repo includes a harness-agnostic [agent skill](skills/ytstudio/SKILL.md) that
teaches any skill-aware AI agent to operate a channel through this CLI, following
the open [SKILL standard](https://agentskills.io).

## Development

Clone the repo, sync dev dependencies, and install the pre-commit hook so
`ruff check` and `ruff format` run on every commit (same checks CI runs):

```bash
uv sync --group dev
uv run pre-commit install
```

Run the suite manually with `uv run pytest` and `uv run pre-commit run --all-files`.

To preview the docs site locally, install the `docs` group and serve with mkdocs:

```bash
uv sync --group docs
uv run mkdocs serve  # or: uv run mkdocs build
```

## API quota

The YouTube Data API enforces a default quota of 10_000 units per project per day. Most read
operations (listing videos, comments, channel info) cost 1 unit, while write operations like
updating video metadata or moderating comments cost 50 units each. Bulk updates can consume quota
quickly. When exceeded, the API returns a 403 error; quota resets at midnight Pacific Time.

| Action | Examples | Approx. cost |
|--------|----------|--------------|
| Read | list videos, comments, playlists; analytics queries | 1 unit |
| Write | update a video, moderate a comment, add or reorder playlist items, schedule a broadcast | 50 units |
| Search | `search.list`, used by `playlists add --from-search` | 100 units |
| Upload | `videos.insert` | ~1600 units |

A full per-operation breakdown lives in the
[API quota docs](https://jdwit.github.io/ytstudio-cli/api-quota/).

You can request a quota increase via **IAM & Admin** → **Quotas** in the
[Google Cloud Console](https://console.cloud.google.com/). See the
[official quota documentation](https://developers.google.com/youtube/v3/getting-started#quota) for
full details.

## Disclaimer

This is not an officially supported Google or YouTube product. YouTube and YouTube Studio are
trademarks of Google. All channel data is accessed exclusively through the official
[YouTube Data API](https://developers.google.com/youtube/v3) and
[YouTube Analytics API](https://developers.google.com/youtube/analytics).
