"""Authentication commands."""

import typer
from rich.console import Console

app = typer.Typer(help="Authentication commands")
console = Console()


@app.command()
def login():
    """Authenticate with YouTube via OAuth."""
    from ytcli.auth import authenticate

    authenticate()


@app.command()
def logout():
    """Remove stored credentials."""
    from ytcli.auth import logout as do_logout

    do_logout()


@app.command()
def status():
    """Show current authentication status."""
    from ytcli.auth import get_status

    get_status()
