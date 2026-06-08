from importlib.resources import files

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

# Source-of-truth ASCII art sits next to this module as `banner.txt`. Edit the
# text file to tweak the art; no code change needed.
BANNER = (files("ytstudio") / "banner.txt").read_text().rstrip("\n")

TAGLINE_LINES = (
    "Manage and analyze your YouTube channel from the terminal.",
    "Designed for humans and AI agents.",
)

# YouTube brand red; "f" cells form the outer ring, everything else is the
# play-button glyph in the centre.
_RED = "#ff0000"
_GLYPH = "bold white"


def _styled_banner() -> Text:
    text = Text(no_wrap=True)
    for ch in BANNER:
        if ch in ("\n", " "):
            text.append(ch)
        elif ch == "f":
            text.append(ch, style=_RED)
        else:
            text.append(ch, style=_GLYPH)
    return text


def render_version_banner(version: str) -> RenderableType:
    """Banner + tagline + version, centred for the --version screen."""
    parts: list[RenderableType] = [Align.center(_styled_banner()), Text("")]
    for line in TAGLINE_LINES:
        parts.append(Align.center(Text(line, style="bold")))
    parts.append(Text(""))
    parts.append(Align.center(Text(f"v{version}", style="dim")))
    return Group(*parts)
