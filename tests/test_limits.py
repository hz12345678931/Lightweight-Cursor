import asyncio
import pytest
from pypilot.agent import Agent, Run
from pypilot.config import Settings
from pypilot.storage import Store
from pypilot.workspace import Workspace
from test_agent import NoMCP, ScriptedModel, call


def fixture(tmp_path, steps):
    settings = Settings(tmp_path / 'data')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'a.py').write_text('x = 1\n')
    ws = Workspace(project)
    store = Store(settings.root / 'sessions.db')
    run = Run(store.create(str(ws.root)), store)
    agent = Agent(settings, store, ws, client=ScriptedModel(steps), mcp=NoMCP())
    return settings, run, agent


async def test_step_limit(tmp_path):
    settings, run, agent = fixture(tmp_path, [call('read', {'path': 'a.py'})])
    settings.values['max_steps'] = 1
    await agent.run(run, 'read')
    assert run.finished and run.events[-1]['reason'] == 'step_limit'


async def test_context_limit_before_request(tmp_path):
    settings, run, agent = fixture(tmp_path, [])
    settings.values['max_context_chars'] = 8000
    await agent.run(run, 'x' * 9000)
    assert run.finished and '预算' in run.events[-1]['text']
    assert not agent.client.seen


async def test_cancel_pending_approval_leaves_no_invalid_history(tmp_path):
    _, run, agent = fixture(tmp_path, [call('write', {'path': 'a.py', 'content': 'changed'})])
    run.task = asyncio.create_task(agent.run(run, 'write'))
    async with asyncio.timeout(3):
        while not run.approvals:
            await asyncio.sleep(.01)
    await run.stop()
    assert (agent.ws.root / 'a.py').read_text() == 'x = 1\n'
    assert run.finished and not run.approvals
    assert not any(m.get('tool_calls') for m in agent.store.load(run.sid, str(agent.ws.root)))


async def test_cancel_before_coroutine_starts(tmp_path):
    _, run, agent = fixture(tmp_path, [])
    run.task = asyncio.create_task(agent.run(run, 'unused'))
    await run.stop()
    assert run.finished
    assert run.events[-1]['reason'] == 'cancelled'


async def test_total_timeout(tmp_path):
    settings, run, agent = fixture(tmp_path, [])
    class SlowModel:
        async def stream(self, messages, schemas):
            await asyncio.sleep(5)
            yield {'type': 'message', 'message': {'role': 'assistant', 'content': 'late'}}
    agent.client = SlowModel()
    settings.values['timeout'] = .1
    await agent.run(run, 'wait', mode='ask')
    assert run.finished and run.events[-1]['reason'] == 'timeout'
