# 参考项目

本项目独立实现应用代码，采用可单独讲解的 Python 后端与轻量界面，未复制整个现成 AI 编辑器改名。依赖许可见 THIRD_PARTY_NOTICES.md。

| 项目 | 参考点 | 本项目的取舍 |
| --- | --- | --- |
| [Cline](https://github.com/cline/cline) | Agent 工具循环、文件/命令审阅、MCP | 自行实现小型循环与 4 个内置工具，不依赖其 VS Code 插件 |
| [Aider](https://github.com/Aider-AI/aider) | 为模型提供仓库级上下文 | 使用 Python AST 简化项目地图，不复刻其多语言排名系统 |
| [Monaco Editor](https://github.com/microsoft/monaco-editor) | 编辑器、差异编辑器、行内建议接口 | 直接依赖 MIT 许可的编辑器库 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | stdio / HTTP 协议实现 | 直接依赖官方 SDK，独立 server 示例可替换 |
| [pywebview](https://github.com/r0x0r/pywebview) | 原生窗口中承载本地前端 | Windows 使用 WebView2，避免另带完整浏览器引擎 |

这些参考解释了实现思路，不代表本预览版具有上述项目的全部能力。课程展示中应明确：Python 项目地图、精确修改、SSE 事件、执行审批、取消与打包逻辑是本项目自己的可读实现。
