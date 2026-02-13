from datetime import UTC, datetime

from rich.console import Console
from rich.table import Table

console = Console()


def create_table(title: str | None = None, show_header: bool = True) -> Table:
    return Table(
        title=title,
        box=None,
        show_header=show_header,
        pad_edge=False,
        collapse_padding=True,
        header_style="dim",
    )


def create_kv_table() -> Table:
    return Table(
        box=None,
        show_header=False,
        pad_edge=False,
        collapse_padding=True,
        padding=(0, 2, 0, 0),
    )


_state = {"raw": False}


def set_raw_output(value: bool):
    _state["raw"] = value


def format_number(n: int) -> str:
    if _state["raw"]:
        return str(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def time_ago(iso_timestamp: str) -> str:
    """Format ISO timestamp as relative time (2h ago, 3d ago)"""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    delta = datetime.now(UTC) - dt

    if delta.days > 365:
        return f"{delta.days // 365}y ago"
    if delta.days > 30:
        return f"{delta.days // 30}mo ago"
    if delta.days > 0:
        return f"{delta.days}d ago"
    if delta.seconds > 3600:
        return f"{delta.seconds // 3600}h ago"
    return "recently"


def dim(text: str) -> str:
    return f"[dim]{text}[/dim]"


def muted(text: str) -> str:
    return f"[dim]{text}[/dim]"


def id_style(text: str) -> str:
    return f"[yellow]{text}[/yellow]"


def cyan(text: str) -> str:
    return f"[cyan]{text}[/cyan]"


def bold(text: str) -> str:
    return f"[bold]{text}[/bold]"


def success(text: str) -> str:
    return f"[green]{text}[/green]"


def success_message(text: str) -> None:
    console.print(f"[green]✓ {text}[/green]")


def error(text: str) -> str:
    return f"[red]{text}[/red]"


def warning(text: str) -> str:
    return f"[yellow]{text}[/yellow]"


def link(text: str, url: str) -> str:
    return f"[cyan][link={url}]{text}[/link][/cyan]"


def truncate(text: str, length: int = 60) -> str:
    if len(text) > length:
        return text[:length] + "..."
    return text
