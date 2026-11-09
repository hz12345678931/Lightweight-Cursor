# 源码运行与 Windows 构建

## 开发环境

Windows 10/11 x64，CPython 3.12，Edge WebView2 Runtime。源代码不需要 Node 构建工具；Monaco 为固定版本的离线静态资源。`requirements-build.txt` 锁定本次使用的依赖，包括测试和打包工具。

在项目根目录的 PowerShell 中执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python scripts/bootstrap_assets.py
.venv\Scripts\python launch.py
```

`bootstrap_assets.py` 从 npm 官方仓库下载 Monaco 0.52.2，从 python.org 下载 Python 3.12.10 嵌入式运行时，并校验固定 SHA-256。pip 25.1.1 安装在内嵌运行时目录。离线安装包已包含这些资源，不会启动时下载编辑器。

## 测试

```powershell
.venv\Scripts\python -m pytest -q
```

这不是调用云端模型的测试。工具和 Agent 测试使用固定响应，MCP 测试实际启动另一个进程并进行协议通信。`test_model.py` 覆盖流式工具参数拼接、截断、断流和错误处理。

界面验收脚本：在临时工作区运行后端，另起终端运行 `python tests/mock_provider.py`，安装 Playwright 后运行 `node tests/ui_smoke.cjs`。它会修改临时示例并新增 `completion_demo.py`，不得对重要项目直接运行。可用 `PYPILOT_URL` 指定后端地址、`PYPILOT_QA_OUTPUT` 指定截图目录。

## 打包

安装 Inno Setup 6，传入本机 `ISCC.exe` 路径：

```powershell
.\scripts\build.ps1 -Python .venv\Scripts\python.exe -ISCC 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

输出：

- `dist/PyPilot/PyPilot.exe`：原生桌面入口。
- `dist/PyPilot/PyPilot-worker.exe`：无界面后端和独立 MCP 工作进程。不要单独移动主程序，需要保留整个目录。
- `dist/installer/PyPilot-Setup-0.1.0.exe`：当前用户安装程序，创建启动入口和卸载入口，不要求管理员权限。

MCP 不能通过无控制台入口提供 stdio，因此构建两个共享依赖目录的入口。安装程序默认放在 `%LOCALAPPDATA%\Programs\PyPilot`，用户数据独立存放。运行命令优先使用项目 `.venv`，否则使用内嵌 Python。安装依赖使用 `python -m pip`。

该预览包尚未购买代码签名证书；项目没有绕过系统安全提示的机制。WebView2 运行时未随包重复分发。如机器缺少 WebView2，请从 [Microsoft 官方页面](https://developer.microsoft.com/microsoft-edge/webview2/) 安装。

发布正式版本前，修改源码和安装器中的版本号、重新运行测试与安装验证，再生成 `v1.0.0` tag 和 Release。本地构建不会自动推送或发布 GitHub。
