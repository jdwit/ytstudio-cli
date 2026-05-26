import typer

from ytstudio import config
from ytstudio.api import authenticate, get_status
from ytstudio.ui import console, create_table, dim, success_message

app = typer.Typer(help="Manage credential profiles (one per YouTube channel)")


@app.command()
def add(
    name: str = typer.Argument(help="Name for the new profile"),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Authenticate by pasting a redirect URL from another browser",
    ),
):
    """Authenticate a new profile and switch to it"""
    if not config.is_valid_profile_name(name):
        console.print(
            "[red]Invalid name. Use letters, digits, '-' and '_' "
            "(must start with a letter or digit).[/red]"
        )
        raise typer.Exit(1)
    if config.profile_exists(name):
        console.print(
            f"[red]Profile '{name}' already exists. "
            f"Switch with 'ytstudio profile use {name}'.[/red]"
        )
        raise typer.Exit(1)

    authenticate(headless=headless, profile=name)
    config.set_active_profile(name)
    success_message(f"Profile '{name}' is now active.")


@app.command("list")
def list_profiles():
    """List configured profiles"""
    profiles = config.list_profiles()
    if not profiles:
        console.print("No profiles yet. Run 'ytstudio login' or 'ytstudio profile add <name>'.")
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
        title = meta.get("title") or dim("unknown (run login for this profile)")
        handle = meta.get("custom_url") or ""
        table.add_row(marker, name, title, handle)

    console.print(table)


@app.command()
def use(name: str = typer.Argument(help="Profile to make active")):
    """Switch the active profile"""
    if not config.profile_exists(name):
        console.print(f"[red]No profile named '{name}'. See 'ytstudio profile list'.[/red]")
        raise typer.Exit(1)
    config.set_active_profile(name)
    success_message(f"Active profile: {name}")


@app.command()
def status(name: str = typer.Argument(None, help="Profile name (default: active)")):
    """Show authentication status for a profile"""
    target = name or config.get_active_profile()
    if not config.profile_exists(target):
        console.print(f"[red]No profile named '{target}'. See 'ytstudio profile list'.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]Profile:[/bold] {target}")
    get_status(target)


@app.command()
def remove(
    name: str = typer.Argument(help="Profile to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a profile and its stored credentials"""
    if not config.profile_exists(name):
        console.print(f"[red]No profile named '{name}'.[/red]")
        raise typer.Exit(1)
    if not force and not typer.confirm(f"Remove profile '{name}' and its stored credentials?"):
        raise typer.Exit()
    config.remove_profile(name)
    success_message(f"Profile '{name}' removed.")
