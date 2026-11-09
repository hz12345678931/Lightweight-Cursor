from __future__ import annotations
import asyncio
import json
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Agent, Run
from .config import Settings, assets_dir
from .mcp_bridge import MCPBridge
from .model import ModelClient
from .storage import Store
from .tools import Tools
from .workspace import Workspace


class Prompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)
    mode: str = "agent"
    session_id: str | None = None
    attachments: list[str] = Field(default_factory=list, max_length=6)


class FileSave(BaseModel):
    path: str
    content: str = Field(max_length=2_000_000)
    version: str


def create_app(settings: Settings | None = None, workspace: str | None = None, token: str | None = None, client=None):
    settings = settings or Settings()
    ws = Workspace(workspace or settings.values["workspace"])
    store = Store(settings.root / "sessions.sqlite3")
    access_token = token or secrets.token_urlsafe(32)
    runs = {}
    app_state = {"workspace": ws, "mcp": MCPBridge(settings)}

    @asynccontextmanager
    async def lifespan(app):
        yield
        for run in runs.values():
            await run.stop()

    app = FastAPI(title="PyPilot", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.token = access_token
    app.state.runs = runs

    def idle():
        if any(not r.finished for r in runs.values()):
            raise HTTPException(409, "请先结束或中断当前任务")

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "跨站请求被拒绝"}, 403)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "来源不匹配"}, 403)
        try:
            if int(request.headers.get("content-length", "0")) > 3_000_000:
                return JSONResponse({"detail": "请求过大"}, 413)
        except ValueError:
            return JSONResponse({"detail": "无效请求"}, 400)
        if request.url.path.startswith("/api/") and not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + access_token):
            return JSONResponse({"detail": "本地会话凭据无效"}, 401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    async def index():
        html = (assets_dir() / "ui/index.html").read_text("utf-8")
        return HTMLResponse(html.replace("__SESSION_TOKEN__", access_token))

    @app.get("/health")
    async def health():
        return {"ok": True, "version": "0.1.0"}

    @app.get("/api/bootstrap")
    async def bootstrap():
        workspace = app_state["workspace"]
        return {"workspace": str(workspace.root), "name": workspace.root.name, "files": workspace.files(), "settings": settings.public(), "sessions": store.sessions(str(workspace.root)), "active_run": next(({"id": r.id, "session_id": r.sid} for r in runs.values() if not r.finished), None)}

    @app.post("/api/workspace")
    async def change_workspace(body: dict):
        idle()
        current = Workspace(body.get("path", ""))
        settings.update({"workspace": str(current.root)})
        app_state["workspace"] = current
        return await bootstrap()

    @app.get("/api/files")
    async def files():
        return app_state["workspace"].files()

    @app.get("/api/file")
    async def file(path: str):
        workspace = app_state["workspace"]
        return {"path": path, "content": workspace.text(path), "version": workspace.version(path)}

    @app.put("/api/file")
    async def save_file(body: FileSave):
        workspace = app_state["workspace"]
        tools = Tools(workspace)
        if workspace.version(body.path) != body.version:
            raise HTTPException(409, "磁盘文件已改变，未覆盖。请重新打开文件后合并修改。")
        prepared = tools.prepare("write", {"path": body.path, "content": body.content})
        # Retain the version the user actually edited rather than a newer snapshot.
        prepared["version"] = body.version
        result = tools.commit(prepared)
        return {**result, "version": workspace.version(body.path)}

    @app.get("/api/search")
    async def search(q: str):
        return await asyncio.to_thread(app_state["workspace"].search, q)

    @app.get("/api/project-map")
    async def project_map(q: str = ""):
        return await asyncio.to_thread(app_state["workspace"].project_map, q)

    @app.get("/api/settings")
    async def get_settings():
        return settings.public()

    @app.post("/api/settings")
    async def set_settings(body: dict):
        idle()
        if "mcp_servers" in body:
            if not isinstance(body["mcp_servers"], list) or len(body["mcp_servers"]) > 7:
                raise ValueError("最多配置 7 个外部 MCP server")
            for config in body["mcp_servers"]:
                if not isinstance(config, dict) or not config.get("name") or not (config.get("command") or config.get("url")) or config.get("bundled"):
                    raise ValueError("每个 MCP 配置需要 name，以及 command/args 或 url")
        settings.update(body)
        return settings.public()

    @app.post("/api/model-test")
    async def model_test():
        try:
            text = ""
            async for event in ModelClient(settings).stream([{"role": "user", "content": "请只回复 OK"}], completion=True):
                if event["type"] == "token":
                    text += event["delta"]
            return {"ok": True, "text": text[:200]}
        except Exception as e:
            raise ValueError(str(e))

    @app.post("/api/completion")
    async def completion(body: dict, request: Request):
        workspace = app_state["workspace"]
        path = str(body.get("path", ""))
        if not path.endswith(".py"):
            return {"text": ""}
        workspace.resolve(path)
        context = (await asyncio.to_thread(workspace.project_map, path, 3000))["summary"]
        task = asyncio.create_task(ModelClient(settings).complete(str(body.get("prefix", ""))[-6000:], str(body.get("suffix", ""))[:2000], path, context))
        try:
            async with asyncio.timeout(25):
                while not task.done():
                    if await request.is_disconnected():
                        task.cancel()
                        return {"text": ""}
                    await asyncio.sleep(0.1)
                return {"text": await task}
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @app.post("/api/sessions")
    async def new_session():
        return {"id": store.create(str(app_state["workspace"].root))}

    @app.get("/api/sessions/{sid}")
    async def session(sid: str):
        messages = store.load(sid, str(app_state["workspace"].root))
        return {"messages": messages, "events": store.events(sid)}

    @app.post("/api/runs")
    async def start(body: Prompt):
        idle()
        if body.mode not in {"ask", "agent"}:
            raise ValueError("模式应为 ask 或 agent")
        workspace = app_state["workspace"]
        sid = body.session_id or store.create(str(workspace.root))
        store.load(sid, str(workspace.root))
        run = Run(sid, store)
        runs[run.id] = run
        for rid in list(runs):
            if len(runs) > 30 and runs[rid].finished:
                del runs[rid]
        agent = Agent(settings, store, workspace, client=client)
        run.task = asyncio.create_task(agent.run(run, body.prompt, body.mode, body.attachments))
        return {"id": run.id, "session_id": sid}

    def get_run(rid):
        if rid not in runs:
            raise HTTPException(404, "运行记录已结束或服务已重启，请查看会话历史")
        return runs[rid]

    @app.get("/api/runs/{rid}/events")
    async def events(rid: str, request: Request, after: int = -1):
        run = get_run(rid)

        async def stream():
            cursor = max(0, after + 1)
            while True:
                run.changed.clear()
                while cursor < len(run.events):
                    item = run.events[cursor]
                    cursor += 1
                    yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if run.finished:
                    break
                if await request.is_disconnected():
                    break
                try:
                    await asyncio.wait_for(run.changed.wait(), 10)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/api/runs/{rid}/cancel")
    async def cancel(rid: str):
        run = get_run(rid)
        await run.stop()
        return {"stopped": run.finished}

    @app.post("/api/runs/{rid}/approve")
    async def approve(rid: str, body: dict):
        get_run(rid).respond(body.get("id"), body.get("accept") is True)
        return {"ok": True}

    @app.post("/api/terminal")
    async def terminal(body: dict):
        idle()
        command = str(body.get("command", ""))
        if not command.strip():
            raise ValueError("请输入命令")
        workspace = app_state["workspace"]
        sid = store.create(str(workspace.root))
        run = Run(sid, store)
        runs[run.id] = run

        async def execute():
            tools = Tools(workspace)
            try:
                run.emit("tool_start", tool="bash", call_id="manual", arguments=json.dumps({"command": command, "timeout": 60}))
                result = await tools.bash(command, 60)
                run.emit("tool_result", tool="bash", call_id="manual", result=result, ok=not result["timed_out"] and result["exit_code"] == 0)
                run.emit("done", reason="completed", text="命令已结束")
            except asyncio.CancelledError:
                run.emit("done", reason="cancelled", text="命令及其子进程已终止")
            except Exception as e:
                run.emit("error", text=str(e))
            finally:
                run.finished = True
                run.changed.set()
        run.task = asyncio.create_task(execute())
        return {"id": run.id, "session_id": sid}

    @app.get("/api/mcp")
    async def mcp_list():
        schemas = await app_state["mcp"].discover()
        return {"servers": app_state["mcp"].status, "tools": schemas}

    @app.post("/api/mcp-test")
    async def mcp_test():
        bridge = app_state["mcp"]
        await bridge.discover()
        name = next((n for n, pair in bridge.routes.items() if pair[0].get("bundled")), None)
        if not name:
            raise ValueError("内置示例 MCP 进程未能连接")
        started = time.monotonic()
        result = await bridge.call(name, {"topic": "test"})
        return {**result, "elapsed_ms": round((time.monotonic() - started) * 1000), "name": name, "transport": "stdio / JSON-RPC"}

    @app.get("/api/trace/{sid}")
    async def trace(sid: str):
        store.load(sid, str(app_state["workspace"].root))
        records = store.events(sid)
        output = "# PyPilot 运行记录\n\n真实工具事件。时间为 Unix 秒。\n\n"
        for record in records:
            output += "```json\n" + json.dumps(record, ensure_ascii=False, indent=2) + "\n```\n\n"
        return PlainTextResponse(output)

    app.mount("/static", StaticFiles(directory=assets_dir() / "ui"), name="static")
    return app

