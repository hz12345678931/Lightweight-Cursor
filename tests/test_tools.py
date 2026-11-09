import asyncio
import json
import os
import time
from pathlib import Path

import pytest
from pypilot.tools import Tools, ToolError
from pypilot.workspace import Workspace


@pytest.fixture
def tools(tmp_path):
    return Tools(Workspace(tmp_path))


def test_pagination_and_line_numbers(tools):
    (tools.ws.root / "a.py").write_text("\n".join(f"line{i}" for i in range(1, 501)), "utf-8")
    result = tools.read("a.py", offset=201, limit=100)
    assert result["text"].startswith("  201 | line201")
    assert result["remaining_lines"] == 200
    assert result["next_offset"] == 301


def test_exact_edit_requires_unique_match(tools):
    file = tools.ws.root / "a.py"
    file.write_text("x = 1\ny = 1\n", "utf-8")
    for old in ["= 1", "absent", ""]:
        with pytest.raises(ToolError):
            tools.prepare("edit", {"path": "a.py", "old": old, "new": "= 2"})
    assert file.read_text() == "x = 1\ny = 1\n"
    patch = tools.prepare("edit", {"path": "a.py", "old": "x = 1", "new": "x = 2"})
    assert "-x = 1" in patch["diff"]
    tools.commit(patch)
    assert file.read_text() == "x = 2\ny = 1\n"


def test_overlapping_occurrences_also_rejected(tools):
    (tools.ws.root / "a.txt").write_text("aaa", "utf-8")
    with pytest.raises(ToolError, match="不唯一"):
        tools.prepare("edit", {"path": "a.txt", "old": "aa", "new": "b"})


def test_stale_preview_cannot_overwrite_user_edit(tools):
    file = tools.ws.root / "a.py"
    file.write_text("x = 1", "utf-8")
    patch = tools.prepare("edit", {"path": "a.py", "old": "x = 1", "new": "x = 2"})
    file.write_text("x = 99", "utf-8")
    with pytest.raises(ToolError, match="发生变化"):
        tools.commit(patch)
    assert file.read_text() == "x = 99"


def test_atomic_write_and_parent_creation(tools, monkeypatch):
    prepared = tools.prepare("write", {"path": "nested/a.py", "content": "value = 42\n"})
    tools.commit(prepared)
    assert (tools.ws.root / "nested/a.py").read_text() == "value = 42\n"
    prepared = tools.prepare("write", {"path": "nested/a.py", "content": "broken"})
    def fail(*args):
        raise OSError("simulated rename failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        tools.commit(prepared)
    assert (tools.ws.root / "nested/a.py").read_text() == "value = 42\n"
    assert not list((tools.ws.root / "nested").glob(".pypilot-*"))


def test_path_and_secrets_boundary(tools):
    for path in ["../outside.txt", ".env", ".env.local", ".git/config", "id_rsa", ".ENV", ".GIT/config", str(tools.ws.root / "absolute.py")]:
        with pytest.raises(ValueError):
            tools.ws.resolve(path)


def test_image_is_multimodal_not_text(tools):
    from PIL import Image
    Image.new("RGB", (2, 2), "red").save(tools.ws.root / "a.png")
    result = tools.read("a.png")
    assert result["image"]["mime"] == "image/png"
    assert "text" not in result


async def test_bash_nonzero_and_output_truncation(tools):
    result = await tools.bash('python -c "import sys; print(\'x\'*20000); print(\'bad\',file=sys.stderr); sys.exit(7)"', 10)
    assert result["exit_code"] == 7
    assert result["truncated"] is True
    assert len(result["stdout"].encode()) <= 16000
    assert "bad" in result["stderr"]


async def test_bash_timeout_kills_child_before_write(tools):
    (tools.ws.root / "slow.py").write_text("import time\nfrom pathlib import Path\ntime.sleep(3)\nPath('should-not-exist').write_text('bad')\n")
    result = await tools.bash("python slow.py", 1)
    assert result["timed_out"]
    await asyncio.sleep(2.5)
    assert not (tools.ws.root / "should-not-exist").exists()
    assert not tools.processes


async def test_bash_cancel_really_stops_process(tools):
    (tools.ws.root / "slow.py").write_text("import time\nfrom pathlib import Path\ntime.sleep(2)\nPath('should-not-exist').write_text('bad')\n")
    task = asyncio.create_task(tools.bash("python slow.py", 20))
    await asyncio.sleep(.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(2)
    assert not (tools.ws.root / "should-not-exist").exists()


def test_python_map_and_ignored_directories(tools):
    (tools.ws.root / "a.py").write_text("import os\nclass A:\n    def run(self):\n        return 1\ndef helper():\n    pass\n")
    (tools.ws.root / ".venv").mkdir()
    (tools.ws.root / ".venv/secret.py").write_text("x=1")
    mapping = tools.ws.project_map("helper")
    assert len(mapping["modules"]) == 1
    assert "def helper" in mapping["summary"]
    assert "def run" in mapping["summary"]
    assert mapping["modules"][0]["imports"] == ["import os"]

