"""MCP client. A fresh bounded stdio/HTTP session avoids orphaned servers."""
from __future__ import annotations
import asyncio
import hashlib
import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


class MCPBridge:
    def __init__(self, settings):
        self.settings = settings
        self.routes = {}
        self.status = []

    def configs(self):
        return [{"name": "python-guide", "bundled": True, "enabled": True}] + self.settings.values.get("mcp_servers", [])

    @asynccontextmanager
    async def connect(self, config):
        if config.get("url"):
            async with streamablehttp_client(config["url"]) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            if config.get("bundled"):
                if getattr(sys, "frozen", False):
                    command, args = str(Path(sys.executable).with_name("PyPilot-worker.exe")), ["--mcp-demo"]
                else:
                    command, args = sys.executable, ["-m", "pypilot.sample_mcp"]
            else:
                from .config import python_command
                command = config["command"].replace("${PYTHON}", python_command())
                args = [str(a).replace("${PYTHON}", python_command()) for a in config.get("args", [])]
            # Inherit only a clean set needed to launch runtimes, not cloud credentials.
            env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ("API_KEY", "SECRET", "TOKEN", "PASSWORD"))}
            env.update(config.get("env", {}))
            params = StdioServerParameters(command=command, args=args, env=env, cwd=str(Path(__file__).resolve().parent.parent) if not getattr(sys, "frozen", False) else None)
            with open(os.devnull, "w") as err:
                async with stdio_client(params, errlog=err) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        yield session

    async def discover(self):
        schemas, routes, status = [], {}, []
        for config in self.configs()[:8]:
            if not config.get("enabled", True):
                continue
            name = config.get("name", "server")
            try:
                async with asyncio.timeout(12):
                    async with self.connect(config) as session:
                        result = await session.list_tools()
                names = []
                for tool in result.tools[:12]:
                    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", name + "_" + tool.name)[:46]
                    exposed = "mcp_" + slug + "_" + hashlib.sha1((name + tool.name).encode()).hexdigest()[:6]
                    routes[exposed] = (config, tool.name)
                    names.append(exposed)
                    schemas.append({"type": "function", "function": {"name": exposed, "description": f"MCP/{name}: {tool.description or tool.name}"[:2000], "parameters": tool.inputSchema}})
                status.append({"name": name, "ok": True, "tools": names, "transport": "HTTP" if config.get("url") else "stdio"})
            except Exception as e:
                status.append({"name": name, "ok": False, "error": f"连接失败（{type(e).__name__}），请检查启动命令或服务地址"})
        self.routes, self.status = routes, status
        return schemas

    async def call(self, name, args):
        if name not in self.routes:
            raise ValueError("MCP 工具未连接，请刷新工具列表")
        config, original = self.routes[name]
        async with asyncio.timeout(40):
            async with self.connect(config) as session:
                result = await session.call_tool(original, args)
        text = "\n".join(getattr(c, "text", "[非文本内容]") for c in result.content)
        return {"server": config["name"], "tool": original, "text": text[:18000], "isError": bool(result.isError), "truncated": len(text) > 18000}

