"""Exercise real SSE parser with provider-shaped streamed HTTP responses."""
import json
import httpx
import pytest
from pypilot.config import Settings
from pypilot.model import ModelClient, ModelError


def fixture_client(tmp_path, monkeypatch, deltas, status=200, done=True):
    settings = Settings(tmp_path)
    settings.values['base_url'] = 'http://127.0.0.1:9999/v1'
    seen = []
    def handle(request):
        seen.append(json.loads(request.content))
        text = ''.join('data: ' + json.dumps({'choices': [d]}) + '\n\n' for d in deltas)
        if done:
            text += 'data: [DONE]\n\n'
        return httpx.Response(status, text=text, headers={'Content-Type': 'text/event-stream'})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    return ModelClient(settings), seen


async def test_stream_assembles_split_tool_arguments(tmp_path, monkeypatch):
    client, seen = fixture_client(tmp_path, monkeypatch, [
        {'delta': {'content': '检查文件'}},
        {'delta': {'tool_calls': [{'index': 0, 'id': 'call_a', 'function': {'name': 'read', 'arguments': '{"path":'}}]}},
        {'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': '"stats.py"}'}}]}, 'finish_reason': 'tool_calls'},
    ])
    events = [e async for e in client.stream([{'role': 'user', 'content': 'test'}])]
    call = events[-1]['message']['tool_calls'][0]
    assert call['id'] == 'call_a'
    assert json.loads(call['function']['arguments']) == {'path': 'stats.py'}
    assert seen[0]['stream'] is True
    assert events[0]['delta'] == '检查文件'


async def test_unfinished_stream_cannot_execute_partial_tool(tmp_path, monkeypatch):
    client, _ = fixture_client(tmp_path, monkeypatch, [{'delta': {'content': 'partial'}}], done=False)
    with pytest.raises(ModelError, match='意外断开'):
        _ = [e async for e in client.stream([])]


async def test_length_and_provider_errors_are_not_success(tmp_path, monkeypatch):
    client, _ = fixture_client(tmp_path, monkeypatch, [{'delta': {}, 'finish_reason': 'length'}])
    with pytest.raises(ModelError, match='长度上限'):
        _ = [e async for e in client.stream([])]


async def test_completion_returns_only_insertion(tmp_path, monkeypatch):
    client, seen = fixture_client(tmp_path, monkeypatch, [{'delta': {'content': '```python\nreturn x + y\n```'}, 'finish_reason': 'stop'}])
    text = await client.complete('def add(x, y):\n    ', '\n', 'a.py', '')
    assert text == 'return x + y'
    assert seen[0]['max_tokens'] == 384


async def test_unauthorized_error_does_not_echo_provider_body(tmp_path, monkeypatch):
    client, _ = fixture_client(tmp_path, monkeypatch, [], status=401)
    with pytest.raises(ModelError, match='API Key 无效'):
        _ = [e async for e in client.stream([])]
