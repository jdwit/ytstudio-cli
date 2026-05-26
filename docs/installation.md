# Installation

ytstudio is published on [PyPI](https://pypi.org/project/ytstudio-cli/) and
runs on Python 3.12 and 3.13.

## With uv (recommended)

[uv](https://uv.io/) installs Python CLIs in isolated environments and keeps
them upgradable.

```bash
uv tool install ytstudio-cli
```

To upgrade later:

```bash
uv tool upgrade ytstudio-cli
```

## With pipx

```bash
pipx install ytstudio-cli
pipx upgrade ytstudio-cli
```

## With pip

```bash
pip install --user ytstudio-cli
```

## Verify

Both names share the same entry point:

```bash
ytstudio --version
yts --version
```

If `--version` prints a version number, you are ready for
[OAuth setup](setup.md).
