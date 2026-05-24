import typer

from ytstudio import config
from ytstudio.api import authenticate, get_status
from ytstudio.ui import console, create_table, dim, success_message

app = typer.Typer(help="Manage YouTube channels (named credential profiles)")


@app.command()
def add(
    name: str = typer.Argument(help="Name for the new channel"),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Authenticate by pasting a redirect URL from another browser",
    ),
):
    """Authenticate a new channel and switch to it"""
    if not config.is_valid_profile_name(name):
        console.print(
            "[red]Invalid name. Use letters, digits, '-' and '_' "
            "(must start with a letter or digit).[/red]"
        )
        raise typer.Exit(1)
    if config.profile_exists(name):
        console.print(
            f"[red]Channel '{name}' already exists. "
            f"Switch with 'ytstudio channel use {name}'.[/red]"
        )
        raise typer.Exit(1)

    authenticate(headless=headless, profile=name)
    config.set_active_profile(name)
    success_message(f"Channel '{name}' is now active.")


@app.command("list")
def list_channels():
    """List configured channels"""
    profiles = config.list_profiles()
    if not profiles:
        console.print("No channels yet. Run 'ytstudio login' or 'ytstudio channel add <name>'.")
        return

    active = config.get_active_profile()
    table = create_table()
    table.add_column("")
    table.add_column("Name")
    table.add_column("YouTube channel")
    table.add_column("Handle")

    for name in profiles:
        meta = config.load_profile_meta(name)
        marker = "[green]*[/green]" if name == active else " "
        title = meta.get("title") or dim("unknown (run login for this channel)")
        handle = meta.get("custom_url") or ""
        table.add_row(marker, name, title, handle)

    console.print(table)


@app.command()
def use(name: str = typer.Argument(help="Channel to make active")):
    """Switch the active channel"""
    if not config.profile_exists(name):
        console.print(f"[red]No channel named '{name}'. See 'ytstudio channel list'.[/red]")
        raise typer.Exit(1)
    config.set_active_profile(name)
    success_message(f"Active channel: {name}")


@app.command()
def status(name: str = typer.Argument(None, help="Channel name (default: active)")):
    """Show authentication status for a channel"""
    target = name or config.get_active_profile()
    if not config.profile_exists(target):
        console.print(f"[red]No channel named '{target}'. See 'ytstudio channel list'.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]Channel:[/bold] {target}")
    get_status(target)


@app.command()
def remove(
    name: str = typer.Argument(help="Channel to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a channel and its stored credentials"""
    if not config.profile_exists(name):
        console.print(f"[red]No channel named '{name}'.[/red]")
        raise typer.Exit(1)
    if not force and not typer.confirm(f"Remove channel '{name}' and its stored credentials?"):
        raise typer.Exit()
    config.remove_profile(name)
    success_message(f"Channel '{name}' removed.")
