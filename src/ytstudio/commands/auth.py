import typer
from rich.console import Console

from ytstudio.auth import authenticate, get_status
from ytstudio.auth import logout as do_logout

app = typer.Typer(help="Authentication commands")
console = Console()


@app.command()
def login():
    """Authenticate with YouTube via OAuth"""
    authenticate()


@app.command()
def logout():
    """Remove stored credentials"""
    do_logout()


@app.command()
def status():
    """Show current authentication status"""
    get_status()
