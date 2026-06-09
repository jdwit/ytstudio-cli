from ytstudio.commands.mcp_cmd import _resolve_allow_write


def test_env_var_enables_write_tools(mock_auth, monkeypatch):
    monkeypatch.setenv("YTSTUDIO_MCP_ALLOW_WRITE", "1")
    assert _resolve_allow_write(allow_write_flag=False, read_only=False) is True


def test_read_only_flag_overrides_env(mock_auth, monkeypatch):
    monkeypatch.setenv("YTSTUDIO_MCP_ALLOW_WRITE", "1")
    assert _resolve_allow_write(allow_write_flag=True, read_only=True) is False
    assert _resolve_allow_write(allow_write_flag=False, read_only=True) is False


def test_flag_beats_unset_env(monkeypatch):
    monkeypatch.delenv("YTSTUDIO_MCP_ALLOW_WRITE", raising=False)
    assert _resolve_allow_write(allow_write_flag=True, read_only=False) is True
    assert _resolve_allow_write(allow_write_flag=False, read_only=False) is False
