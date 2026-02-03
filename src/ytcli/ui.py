"""Centralized UI components and styling."""

from rich.console import Console
from rich.table import Table

console = Console()


def create_table(title: str | None = None, show_header: bool = True) -> Table:
    """Create a table with consistent styling."""
    return Table(
        title=title,
        box=None,
        show_header=show_header,
        pad_edge=False,
        collapse_padding=True,
        header_style="dim",
    )


def create_kv_table() -> Table:
    """Create a key-value table (for details view)."""
    return Table(
        box=None,
        show_header=False,
        pad_edge=False,
        collapse_padding=True,
        padding=(0, 2, 0, 0),
    )


def format_number(n: int) -> str:
    """Format large numbers (1234567 -> 1.2M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def dim(text: str) -> str:
    """Dim text."""
    return f"[dim]{text}[/dim]"


def success(text: str) -> str:
    """Green success text."""
    return f"[green]{text}[/green]"


def error(text: str) -> str:
    """Red error text."""
    return f"[red]{text}[/red]"


def warning(text: str) -> str:
    """Yellow warning text."""
    return f"[yellow]{text}[/yellow]"


def link(text: str, url: str) -> str:
    """Clickable link."""
    return f"[link={url}]{text}[/link]"
