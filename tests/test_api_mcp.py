import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from pypilot.config import Settings
from pypilot.server import create_app
from pypilot.mcp_bridge import MCPBridge


def test_api_auth_conflicts_and_key_not_exposed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.py").write_text("x=1")
    settings = Settings(tmp_path / "data")
    settings.update({"api_key": "test-secret-not-a-real-key"})
    app = create_app(settings, str(workspace), "test-session-token")
    with TestClient(app) as client:
        assert client.get("/api/bootstrap").status_code == 401
        headers = {"Authorization": "Bearer test-session-token"}
        response = client.get("/api/bootstrap", headers=headers)
        assert response.status_code == 200
        assert "test-secret-not-a-real-key" not in response.text
        assert "encrypted_key" not in response.text
        assert client.get("/api/file?path=../a.py", headers=headers).status_code == 400
        response = client.put("/api/file", headers=headers, json={"path": "a.py", "content": "overwrite", "version": "stale"})
        assert response.status_code == 409
        assert (workspace / "a.py").read_text() == "x=1"
        assert client.post("/api/settings", headers={**headers, "Origin": "https://evil.example"}, json={}).status_code == 403


async def test_real_stdio_mcp_roundtrip(tmp_path):
    bridge = MCPBridge(Settings(tmp_path))
    schemas = await bridge.discover()
    assert schemas, bridge.status
    name = schemas[0]["function"]["name"]
    result = await bridge.call(name, {"topic": "test"})
    assert result["server"] == "python-guide"
    assert result["isError"] is False
    assert "unittest" in result["text"]
