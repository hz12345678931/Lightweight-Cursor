# 老师要求对照

依据用户提供的《Python智能体专题_3x40min.pptx》作业部分。这里区分已实现的能力与需要真实开发周期、模型服务或现场演示才能完成的交付要求。

| 要求 | 实现 / 证据 | 状态 |
| --- | --- | --- |
| 可双击、带标题栏的独立桌面应用 | pywebview + WebView2，Windows exe 与安装器 | 已实现，预览版 |
| 文件树 / 编辑器 / 对话与工具三栏 | 本地 Monaco 编辑器 | 已实现 |
| 后端可以独立启动，curl 观察流式事件 | `--headless`、HTTP API、SSE | 已实现 |
| Agent + read/write/edit/bash | `pypilot/agent.py`、`pypilot/tools.py` | 已实现 |
| read 行号、分页、剩余行数 | offset 从 1 开始，limit 上限 400 | 测试覆盖 |
| 图片返回真正多模态内容 | base64 image_url 内容块；不以伪文本代替 | 结构已测试，需支持视觉的真实模型联调 |
| write 自动建目录、原子替换、行数 | 临时文件 + fsync + os.replace | 测试覆盖 |
| edit 仅精确且唯一匹配 | 不存在 / 多重 / 重叠匹配均拒绝 | 测试覆盖 |
| bash stdout/stderr/exit code | 非零结果返回模型，界面红色显示 | 测试覆盖 |
| bash 超时、截断、真正停止 | 限时、双流限长、Windows Job Object 终止子进程树 | 测试覆盖 |
| 工具可见、diff、失败恢复 | SSE 事件、审阅框、错误返回下一轮 | 本地协议验收 |
| 防止无限循环 | 步数上限、重复调用限制、整体超时、上下文字符预算 | 已实现 |
| 真实 MCP 调用 | SDK 连接独立 python-guide 进程；非直接调用本地函数 | 真实协议已测试 |
| 公共 GitHub 仓库 | [hz12345678931/Lightweight-Cursor](https://github.com/hz12345678931/Lightweight-Cursor) | 已建立，按真实迭代提交 |
| ≥15 commits、跨度 ≥7 天 | 应按真实迭代逐步积累，不能倒填日期 | 尚未满足 |
| v1.0.0 tag + Release 安装包 | 当前仅 0.1.0 preview | 正式发布待完成 |
| README ≤3 步、≥3 张截图 | README 三步启动 + 截图 | 已准备 |
| .env.example、不提交密钥 | 环境变量示例、DPAPI、.gitignore | 已准备 |
| trace.md 含失败与恢复 | 本地固定模型响应 + 实际工具执行 | 已准备；提交前补真实模型记录 |
| report.md / 构建说明 | 报告与 build.md | 已准备初稿 |
| demo.mp4 / 5 分钟现场演示 | demo-script.md 提供流程 | 需配置真实模型后录制，不能用协议测试冒充 |

额外实现用户要求：Python AI 行内补全、AI 对话、差异修改、Python 项目地图、Agent 任务执行。暂不做全语言语义分析和复杂插件市场。

`python-guide` 是项目自带的独立示例 server。它证明 MCP 握手、发现和调用链路，但不是联网知识检索。如果老师要求使用指定的第三方 server，请在 MCP 面板增加该 server，再录制一次它的真实调用。
