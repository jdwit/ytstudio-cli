import builtins
import json
import sys

import pytest
from typer.testing import CliRunner

from ytstudio.main import app

runner = CliRunner()


class TestPrintConfig:
    def test_print_config_claude_desktop_outputs_valid_json(self):
        result = runner.invoke(app, ["mcp", "print-config"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "mcpServers" in payload
        assert "ytstudio" in payload["mcpServers"]
        assert payload["mcpServers"]["ytstudio"]["command"]
        assert payload["mcpServers"]["ytstudio"]["args"][:2] in (
            ["mcp", "serve"],
            ["-m", "ytstudio"],
        )

    def test_print_config_allow_write_sets_env(self):
        result = runner.invoke(app, ["mcp", "print-config", "--allow-write"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        env = payload["mcpServers"]["ytstudio"].get("env") or {}
        assert env == {"YTSTUDIO_MCP_ALLOW_WRITE": "1"}

    def test_print_config_no_fastmcp_import(self, monkeypatch):
        # Even when fastmcp cannot be imported, print-config must work.
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("fastmcp"):
                raise ImportError("fastmcp blocked for this test")
            return real_import(name, *args, **kwargs)

        # Snapshot module state so we can restore it for downstream tests.
        original = {
            k: v for k, v in sys.modules.items() if k.startswith(("fastmcp", "ytstudio.mcp"))
        }
        for mod in list(original):
            sys.modules.pop(mod, None)
        try:
            monkeypatch.setattr(builtins, "__import__", fake_import)
            result = runner.invoke(app, ["mcp", "print-config", "--name", "yt"])
        finally:
            for k, v in original.items():
                sys.modules[k] = v

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "yt" in payload["mcpServers"]


class TestTools:
    def test_tools_table_shows_read_only_tools(self, mock_auth):
        result = runner.invoke(app, ["mcp", "tools"])
        assert result.exit_code == 0
        for name in ("list_videos", "whoami", "analytics_overview"):
            assert name in result.stdout
        assert "update_video" not in result.stdout

    def test_tools_with_allow_write_shows_write_tools(self, mock_auth):
        result = runner.invoke(app, ["mcp", "tools", "--allow-write"])
        assert result.exit_code == 0
        for name in ("update_video", "create_playlist", "delete_playlist"):
            assert name in result.stdout

    def test_tools_json_output_is_valid_schema(self, mock_auth):
        result = runner.invoke(app, ["mcp", "tools", "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert payload
        entry = payload[0]
        for key in ("name", "description", "inputSchema", "annotations"):
            assert key in entry


class TestServeMissingFastmcp:
    def test_serve_missing_fastmcp_shows_friendly_error(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "fastmcp" or name.startswith("fastmcp."):
                raise ImportError("simulated missing fastmcp")
            return real_import(name, *args, **kwargs)

        original = {
            k: v for k, v in sys.modules.items() if k.startswith(("fastmcp", "ytstudio.mcp"))
        }
        for mod in list(original):
            sys.modules.pop(mod, None)
        try:
            monkeypatch.setattr(builtins, "__import__", fake_import)
            result = runner.invoke(app, ["mcp", "serve"])
        finally:
            for k, v in original.items():
                sys.modules[k] = v

        assert result.exit_code == 1
        assert "MCP support requires fastmcp" in result.stdout


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("YTSTUDIO_MCP_ALLOW_WRITE", raising=False)
