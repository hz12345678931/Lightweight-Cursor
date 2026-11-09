import asyncio
import json
import pytest
from pypilot.agent import Agent, Run
from pypilot.config import Settings
from pypilot.storage import Store
from pypilot.workspace import Workspace


class NoMCP:
    status = []
    async def discover(self):
        return []


class ScriptedModel:
    """Deterministic protocol fixture, not a product model or offline AI."""
    def __init__(self, steps):
        self.steps = iter(steps)
        self.seen = []

    async def stream(self, messages, schemas):
        self.seen.append(messages)
        message = next(self.steps)
        if message.get("content"):
            yield {"type": "token", "delta": message["content"]}
        yield {"type": "message", "message": message}


def call(name, args, id="call1"):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


async def run_fixture(tmp_path, steps, accept=True):
    settings = Settings(tmp_path / "data")
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "stats.py").write_text("def mean(nums):\n    if not nums:\n        return 0\n    return sum(nums) / len(nums)\n")
    ws = Workspace(workspace)
    store = Store(settings.root / "sessions.db")
    sid = store.create(str(ws.root))
    run = Run(sid, store)
    model = ScriptedModel(steps)
    agent = Agent(settings, store, ws, client=model, mcp=NoMCP())
    run.task = asyncio.create_task(agent.run(run, "修复 mean 的空列表行为，并验证"))
    while not run.finished:
        for aid in list(run.approvals):
            if not run.approvals[aid].done():
                run.respond(aid, accept)
        await asyncio.sleep(.01)
    await run.task
    return run, ws, model, store


async def test_agent_failure_recovery_and_real_test_command(tmp_path):
    steps = [
        call("edit", {"path": "stats.py", "old": "not here", "new": "wrong"}),
        call("read", {"path": "stats.py"}, "call2"),
        call("edit", {"path": "stats.py", "old": "        return 0", "new": "        raise ValueError('empty')"}, "call3"),
        call("bash", {"command": 'python -c "from stats import mean; print(mean([2,4]))"', "timeout": 10}, "call4"),
        {"role": "assistant", "content": "修改完成，正常输入测试输出 3.0；空输入回归测试尚未执行。"},
    ]
    run, ws, model, store = await run_fixture(tmp_path, steps)
    results = [e for e in run.events if e["type"] == "tool_result"]
    assert results[0]["ok"] is False
    assert results[-1]["result"]["exit_code"] == 0
    assert "3.0" in results[-1]["result"]["stdout"]
    assert "raise ValueError" in ws.text("stats.py")
    assert any(e["type"] == "approval" for e in run.events)
    assert store.events(run.sid)
    assert run.events[-1]["reason"] == "completed"


async def test_rejection_does_not_write(tmp_path):
    steps = [call("write", {"path": "a.py", "content": "danger"}), {"role": "assistant", "content": "用户拒绝，未写入。"}]
    run, ws, _, _ = await run_fixture(tmp_path, steps, accept=False)
    assert not (ws.root / "a.py").exists()
    assert any(e["type"] == "tool_result" and not e["ok"] for e in run.events)


async def test_repeat_guard(tmp_path):
    steps = [call("read", {"path": "stats.py"}, str(i)) for i in range(5)]
    run, _, _, _ = await run_fixture(tmp_path, steps)
    assert run.events[-1]["type"] == "error"
    assert "死循环" in run.events[-1]["text"]


async def test_unknown_tool_is_not_executed(tmp_path):
    steps = [call("delete_everything", {}), {"role": "assistant", "content": "工具不可用"}]
    run, _, _, _ = await run_fixture(tmp_path, steps)
    assert any(e["type"] == "tool_result" and "白名单" in e["result"].get("error", "") for e in run.events)

