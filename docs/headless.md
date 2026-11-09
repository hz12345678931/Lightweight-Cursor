# 独立后端与流式事件

PowerShell 启动（源码）：

```powershell
$env:PYPILOT_SESSION_TOKEN = 'local-demo-token'
.venv\Scripts\python launch.py --headless --workspace 'C:\your\python-project' --port 8765
```

安装后使用 `PyPilot-worker.exe` 代替上述 Python 命令。只绑定 `127.0.0.1`；不把端口暴露到局域网。独立模式会打印本地会话凭据，课堂演示可指定临时值。

另起 PowerShell：

```powershell
$headers = @{Authorization='Bearer local-demo-token'}
$body = @{prompt='解释这个项目'; mode='ask'} | ConvertTo-Json
$run = Invoke-RestMethod 'http://127.0.0.1:8765/api/runs' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
curl.exe -N -H 'Authorization: Bearer local-demo-token' "http://127.0.0.1:8765/api/runs/$($run.id)/events"
```

事件包括 `user / context / step / token / assistant / tool_start / approval / tool_result / done / error`。每项有递增 id；用 `?after=上次id` 重连。`done` 的 reason 区分完成、取消、超时和步数上限。

Agent 模式的写入、命令和 MCP 会暂停，等待明确回复：

```powershell
$approval = @{id='复制事件中的 approval_id'; accept=$true} | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8765/api/runs/$($run.id)/approve" -Method Post -Headers $headers -ContentType 'application/json' -Body $approval
Invoke-RestMethod "http://127.0.0.1:8765/api/runs/$($run.id)/cancel" -Method Post -Headers $headers
```

模型配置可通过桌面界面设置；或者在启动前设 `PYPILOT_BASE_URL`、`PYPILOT_MODEL`、`PYPILOT_API_KEY` 环境变量。`.env.example` 仅为变量名示例，本版本不会自动读取 `.env` 文件。不要把真实 API Key 放入命令示例、截图或 Git。

MCP 配置示例：

```json
[
  {"name":"custom-python-server","command":"${PYTHON}","args":["C:/absolute/path/server.py"]},
  {"name":"http-server","url":"http://127.0.0.1:8000/mcp"}
]
```

`${PYTHON}` 替换为应用内嵌解释器；外部 server 需要的依赖必须安装到所指定的 Python 环境。stdio 每次调用建立有超时的会话。当前没有复杂插件系统和 OAuth 登录流程，配置文件中的外部 MCP `env` 值不会使用 DPAPI 加密；不要在其中填写长期密钥。
