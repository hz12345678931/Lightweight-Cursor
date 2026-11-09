"""A separate real MCP server, not a mocked local function call."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("python-guide")


@mcp.tool()
def python_tip(topic: str) -> str:
    """查询 Python 测试、异常、文件操作的简短实践建议。用于演示真实外部 MCP 协议往返。"""
    notes = {
        "test": "使用 python -m unittest discover -v 执行测试。覆盖正常输入、空输入和错误输入，非零退出码表示测试失败。",
        "exception": "无效参数可抛出 ValueError，类型错误可抛出 TypeError。只捕获能够处理的异常，保留可读错误信息。",
        "file": "使用 pathlib 管理路径，UTF-8 明确编码，先写同目录临时文件再用 os.replace 原子替换。",
    }
    query = topic.lower()
    key = "test" if "测" in query or "test" in query else "exception" if "异常" in query or "exception" in query else "file"
    return f"[python-guide / MCP 独立进程] {notes[key]}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

