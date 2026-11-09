"""Local deterministic OpenAI-compatible fixture, NEVER a real AI service.

Usage: python tests/mock_provider.py --port 8877
Only listens on loopback. The real app still owns every file/command/MCP action.
"""
import argparse
import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()


def tool(name, args):
    return {'tool_calls': [{'index': 0, 'id': 'fixture_call', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}]}


@app.post('/v1/chat/completions')
async def completion(request: Request):
    body = await request.json()
    messages = body['messages']
    latest = next((m['content'] for m in reversed(messages) if m['role'] == 'user' and isinstance(m.get('content'), str)), '')
    if '代码补全器' in messages[0]['content']:
        delta = {'content': 'return a + b'}
    elif latest == '请只回复 OK':
        delta = {'content': 'OK · local protocol fixture (not AI)'}
    elif not body.get('tools'):
        delta = {'content': '【本地协议测试响应，非真实 AI】项目包含 stats.py 和 test_stats.py。mean 与 median 分别计算平均值和中位数，unittest 覆盖正常输入和空输入。'}
    elif '停止测试' in latest:
        delta = tool('bash', {'command': 'python -c "import time; time.sleep(30)"', 'timeout': 60})
    else:
        count = sum(m['role'] == 'tool' for m in messages)
        steps = [
            tool('read', {'path': 'missing_stats.py'}),
            tool('read', {'path': 'stats.py'}),
            tool('read', {'path': 'test_stats.py'}),
            tool('bash', {'command': 'python -m unittest discover -v', 'timeout': 20}),
            tool('edit', {'path': 'stats.py', 'old': '        return 0  # 待修复：这个行为与函数约定不一致',
                          'new': '        raise ValueError("numbers must not be empty")'}),
            tool('bash', {'command': 'python -m unittest discover -v', 'timeout': 20}),
        ]
        if count < len(steps):
            delta = steps[count]
        elif count == len(steps):
            name = next(t['function']['name'] for t in body['tools'] if t['function']['name'].startswith('mcp_') and 'python_tip' in t['function']['name'])
            delta = tool(name, {'topic': 'test'})
        else:
            delta = {'content': '【本地协议测试完成，非真实 AI】\n真实工具已读文件、展示差异并修改 mean 的空列表分支，5 项 unittest 测试通过。独立 MCP 进程已返回测试建议。首次读取不存在文件和首次测试失败，均保留在记录中。'}

    async def events():
        # Split text / tool arguments over multiple SSE chunks to exercise assembly.
        if delta.get('content'):
            for start in range(0, len(delta['content']), 8):
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': delta['content'][start:start+8]}}]}, ensure_ascii=False) + '\n\n'
                await asyncio.sleep(.035)
        else:
            call = delta['tool_calls'][0]
            args = call['function'].pop('arguments')
            yield 'data: ' + json.dumps({'choices': [{'delta': delta}]}) + '\n\n'
            for start in range(0, len(args), 14):
                chunk = {'tool_calls': [{'index': 0, 'function': {'arguments': args[start:start+14]}}]}
                yield 'data: ' + json.dumps({'choices': [{'delta': chunk}]}, ensure_ascii=False) + '\n\n'
                await asyncio.sleep(.01)
        reason = 'tool_calls' if 'tool_calls' in delta else 'stop'
        yield 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': reason}]}) + '\n\n'
        yield 'data: [DONE]\n\n'
    return StreamingResponse(events(), media_type='text/event-stream')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning')
