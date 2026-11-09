# 0.1.0 预览版验证记录

验证日期：2026-11-09。平台：Windows 11 x64。

## 已执行

| 范围 | 结果 |
| --- | --- |
| 工具、Agent、HTTP、模型协议、真实 MCP | 22 项 pytest 通过 |
| 步数、上下文、等待确认时取消、启动前取消、整体超时 | 5 项 pytest 通过 |
| 打包后的 TLS 初始化 | `PyPilot-worker.exe --diagnostics` 成功 |
| 原生安装 | 安装器退出码 0；安装目录存在主程序、worker、依赖与内嵌 Python |
| 测试副本卸载 | 卸载退出码 0，临时安装主程序已移除；交付安装包和源码保留 |
| 安装版启动 | 原生 PyPilot.exe 窗口出现；控件树含文件树、Monaco 编辑器、对话、项目地图和设置 |
| 打包版 UI 自动化 | 9 项流程通过；JavaScript page errors 为 0 |

UI 流程包含：打开编辑器、Python AST 地图、独立 MCP 真实调用、OpenAI 兼容 SSE、失败恢复、差异审阅、真实 unittest、行内补全后 Tab 接受、停止任务。

协议验收流程首先读取不存在的文件，收到真实错误；随后读取正确文件，运行示例得到 1 项失败，审阅并写入空列表分支修复，再运行 5 项测试全部通过，最后通过独立 MCP 进程调用 python_tip。截图、`trace.md` 和 `ui-result.json` 来自该次执行。

补全和 Agent 的模型文本由 `tests/mock_provider.py` 固定提供，界面也明确标注 `local-protocol-fixture-NOT-AI`。没有调用用户的云端账户，没有使用或保存真实 API Key。该验证证明程序链路可用，不代表任何真实模型的任务成功率。

## 修复过的实际问题

- PowerShell 命令嵌套引号与非零退出码：改为 EncodedCommand 并传播原生程序退出码。
- 取消后 Python 子进程仍存活：使用 Windows Job Object，并将输出管道读取纳入整体超时。
- 嵌入式 Python 无法导入工作区模块：加入当前工作区的 site 路径，用真实 unittest 检验。
- 冻结程序 TLS 初始化失败：随包保留构建用 Python 发行版所需的证书信任策略资源，未关闭证书校验。
- MCP 在无控制台程序中没有 stdio：提供独立控制台 worker，打包版实际通信通过。

## 尚未验证

真实模型的补全质量、工具调用稳定性、多模态图片支持；其他 Windows 机器的全新安装环境；第三方 MCP server 的特定依赖与认证；正式 GitHub Release 和现场演示。

当前 pytest 有 1 条上游 Starlette TestClient 的 httpx 迁移提示，不影响测试通过。只有 Windows x64 被构建与验证。
