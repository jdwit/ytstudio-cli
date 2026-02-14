LOGO = """
[red]        ██████████████[/red]
[red]    ████[/red][white]██████████████[/white][red]████[/red]
[red]  ████[/red][white]██████████████████████[/white][red]████[/red]
[red] ███[/red][white]████████████████████████████[/white][red]███[/red]
[red] ███[/red][white]██████████[/white][red]██[/red][white]████████████████[/white][red]███[/red]
[red]████[/red][white]█████████[/white][red]████[/red][white]██████████████[/white][red]████[/red]
[red]████[/red][white]████████[/white][red]██████[/red][white]████████████[/white][red]████[/red]
[red]████[/red][white]████████[/white][red]████████[/red][white]██████████[/white][red]████[/red]
[red]████[/red][white]████████[/white][red]██████[/red][white]████████████[/white][red]████[/red]
[red]████[/red][white]█████████[/white][red]████[/red][white]██████████████[/white][red]████[/red]
[red] ███[/red][white]██████████[/white][red]██[/red][white]████████████████[/white][red]███[/red]
[red] ███[/red][white]████████████████████████████[/white][red]███[/red]
[red]  ████[/red][white]██████████████████████[/white][red]████[/red]
[red]    ████[/red][white]██████████████[/white][red]████[/red]
[red]        ██████████████[/red]"""


def get_banner(version: str) -> str:
    return f"{LOGO}\n\n  [bold white]ytstudio[/bold white] [dim]v{version}[/dim]"
