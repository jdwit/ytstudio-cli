"""`ytstudio mcp` sub-app: serve, tools, print-config.

fastmcp is imported lazily inside serve/tools so that the rest of the CLI
boots without paying the import cost (and works at all when fastmcp is not
installed).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from enum import StrEnum

import typer

from ytstudio.config import get_active_profile
from ytstudio.ui import console, create_table

app = typer.Typer(help="Run ytstudio as an MCP server for AI agents.")

INSTALL_HINT = (
    "MCP support requires fastmcp. Install with "
    "`uv tool install ytstudio-cli[mcp]` or `pip install fastmcp`."
)


class Transport(StrEnum):
    stdio = "stdio"
    http = "http"


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


class ToolsOutput(StrEnum):
    table = "table"
    json = "json"


class ClientKind(StrEnum):
    claude_desktop = "claude-desktop"
    cursor = "cursor"
    generic = "generic"


def _resolve_allow_write(allow_write_flag: bool, read_only: bool) -> bool:
    """--read-only > --allow-write > YTSTUDIO_MCP_ALLOW_WRITE=1 > False."""
    if read_only:
        return False
    if allow_write_flag:
        return True
    return os.environ.get("YTSTUDIO_MCP_ALLOW_WRITE") == "1"


def _load_server_module():
    try:
        # Lazy: keep fastmcp out of the cold-start path for non-MCP commands.
        from ytstudio.mcp import server as server_module  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] == "fastmcp":
            console.print(f"[red]{INSTALL_HINT}[/red]")
            raise typer.Exit(1) from exc
        raise
    except ImportError as exc:
        console.print(f"[red]{INSTALL_HINT}[/red]")
        raise typer.Exit(1) from exc
    return server_module


@app.command("serve")
def serve(
    transport: Transport = typer.Option(
        Transport.stdio, "--transport", help="Transport: stdio or http"
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (http only)"),
    port: int = typer.Option(8765, "--port", help="Bind port (http only)"),
    profile: str = typer.Option(None, "--profile", help="Profile name (defaults to active)"),
    allow_write: bool = typer.Option(
        False,
        "--allow-write",
        help="Expose write tools. Also honors YTSTUDIO_MCP_ALLOW_WRITE=1; flag wins.",
    ),
    read_only: bool = typer.Option(
        False,
        "--read-only",
        help="Force read-only; overrides --allow-write and the env var.",
    ),
    log_level: LogLevel = typer.Option(LogLevel.info, "--log-level", help="Log level"),
):
    """Start the MCP server."""
    # Resolve the fastmcp import first so the missing-dependency message goes
    # to stdout (and can be captured in tests). Only after that do we redirect
    # the rich console to stderr for the stdio JSON-RPC transport.
    server_module = _load_server_module()

    if transport is Transport.stdio:
        console.file = sys.stderr

    if host == "0.0.0.0" and transport is Transport.http:
        print(
            "ytstudio MCP: binding to 0.0.0.0 exposes the server on the network "
            "without authentication. Use only on trusted networks.",
            file=sys.stderr,
        )
    effective_write = _resolve_allow_write(allow_write, read_only)
    resolved_profile = profile or get_active_profile()
    mcp = server_module.build_server(profile=resolved_profile, allow_write=effective_write)

    if transport is Transport.http:
        print(
            f"ytstudio MCP serving on http://{host}:{port} (profile={resolved_profile}, "
            f"write={'on' if effective_write else 'off'}, log_level={log_level.value})",
            file=sys.stderr,
        )
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()


@app.command("tools")
def tools(
    output: ToolsOutput = typer.Option(ToolsOutput.table, "--output", "-o", help="Output format"),
    allow_write: bool = typer.Option(
        False, "--allow-write", help="Preview the tool list as if writes were enabled"
    ),
    profile: str = typer.Option(None, "--profile", help="Profile (defaults to active)"),
):
    """List the MCP tools the server would expose."""
    import asyncio  # noqa: PLC0415

    server_module = _load_server_module()
    resolved_profile = profile or get_active_profile()
    mcp = server_module.build_server(profile=resolved_profile, allow_write=allow_write)
    tool_list = asyncio.run(mcp.list_tools())

    if output is ToolsOutput.json:
        payload = []
        for tool in tool_list:
            ann = tool.annotations
            ann_dict: dict[str, object] = {}
            if ann is not None:
                for field_name in ("title", "readOnlyHint", "destructiveHint", "openWorldHint"):
                    value = getattr(ann, field_name, None)
                    if value is not None:
                        ann_dict[field_name] = value
            payload.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.parameters,
                    "annotations": ann_dict,
                }
            )
        print(json.dumps(payload, indent=2))
        return

    table = create_table()
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Read-only")
    table.add_column("Destructive")
    for tool in sorted(tool_list, key=lambda t: t.name):
        first_line = (tool.description or "").split("\n", 1)[0]
        read_only = getattr(tool.annotations, "readOnlyHint", None) if tool.annotations else None
        destructive = (
            getattr(tool.annotations, "destructiveHint", None) if tool.annotations else None
        )
        table.add_row(
            tool.name,
            first_line,
            "yes" if read_only else "no",
            "yes" if destructive else "no",
        )
    console.print(table)


@app.command("print-config")
def print_config(
    client: ClientKind = typer.Option(
        ClientKind.claude_desktop, "--client", help="Target MCP client"
    ),
    name: str = typer.Option("ytstudio", "--name", help="Server name inside the client config"),
    allow_write: bool = typer.Option(
        False, "--allow-write", help="Embed YTSTUDIO_MCP_ALLOW_WRITE=1 in the env block"
    ),
):
    """Print a ready-to-paste MCP client config snippet.

    No API calls and no fastmcp import; works even on machines without the
    optional dependency installed.
    """
    executable = shutil.which("ytstudio")
    if executable:
        command = executable
        args = ["mcp", "serve"]
    else:
        command = sys.executable
        args = ["-m", "ytstudio", "mcp", "serve"]

    env: dict[str, str] = {}
    if allow_write:
        env["YTSTUDIO_MCP_ALLOW_WRITE"] = "1"

    server_block: dict[str, object] = {"command": command, "args": args}
    if env:
        server_block["env"] = env

    if client is ClientKind.cursor:
        payload = {"mcpServers": {name: server_block}}
    else:
        payload = {"mcpServers": {name: server_block}}

    print(json.dumps(payload, indent=2))
