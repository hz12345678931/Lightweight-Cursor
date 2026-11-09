"""The four model-facing tools. No fuzzy edits, shell output always bounded."""
from __future__ import annotations

import asyncio
import base64
import difflib
import json
import mimetypes
import os
import shutil
import signal
import subprocess
import tempfile
import sys
from pathlib import Path
from .workspace import Workspace


def definition(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}


SCHEMAS = [
    definition("read", "读取工作区文件。文本带行号，offset 从 1 开始，limit 最多 400 行；图片返回多模态图像。", {"path": {"type": "string"}, "offset": {"type": "integer", "minimum": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 400}}, ["path"]),
    definition("write", "创建文件或明确要求的完整文件写入。已有文件的局部修改必须使用 edit。自动建父目录，原子写入。", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    definition("edit", "精确替换一次字符串。old 必须非空且只出现一次；不唯一或找不到时先 read 扩充上下文，禁止猜测。", {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, ["path", "old", "new"]),
    definition("bash", "在工作区执行命令（搜索、Git、依赖安装、测试）。Windows 优先 Git Bash，否则 PowerShell。必须设置 timeout，返回 stdout/stderr/exit_code，非零是正常工具结果。", {"command": {"type": "string"}, "timeout": {"type": "integer", "minimum": 1, "maximum": 120}}, ["command", "timeout"]),
]


class ToolError(ValueError):
    pass


class Tools:
    def __init__(self, workspace: Workspace):
        self.ws = workspace
        self.processes: set[asyncio.subprocess.Process] = set()
        self.jobs = {}

    def read(self, path: str, offset=1, limit=200) -> dict:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 1 or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 400:
            raise ToolError("offset 从 1 开始，limit 应为 1–400")
        p = self.ws.resolve(path)
        if not p.is_file():
            raise ToolError(f"文件不存在：{path}。请先搜索正确的相对路径。")
        mime = mimetypes.guess_type(p.name)[0]
        if mime in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            if p.stat().st_size > 5_000_000:
                raise ToolError("图片超过 5 MB，请缩小后重试")
            return {"path": path, "image": {"mime": mime, "data": base64.b64encode(p.read_bytes()).decode()}, "summary": f"读取图片 {path}"}
        if p.stat().st_size > 20_000_000:
            raise ToolError("文件超过 20 MB，请通过 bash 检索片段")
        lines = self.ws.decode(p.read_bytes()).splitlines()
        selected, chars = [], 0
        for number, line in enumerate(lines[offset - 1:offset - 1 + limit], offset):
            clipped = line[:3000]
            if chars + len(clipped) > 18000:
                break
            selected.append(f"{number:>5} | {clipped}" + (" … [此行截断]" if len(line) > 3000 else ""))
            chars += len(clipped)
        remaining = max(0, len(lines) - (offset - 1 + len(selected)))
        return {"path": path, "text": "\n".join(selected), "total_lines": len(lines), "remaining_lines": remaining, "next_offset": offset + len(selected) if remaining else None}

    def prepare(self, name: str, args: dict) -> dict:
        if name not in {"edit", "write"}:
            raise ToolError("不能为此工具创建文件预览")
        path = args.get("path", "")
        target = self.ws.resolve(path)
        old_text = self.ws.text(path) if target.exists() else ""
        if name == "edit":
            if not target.is_file():
                raise ToolError(f"文件不存在：{path}")
            old, new = args.get("old"), args.get("new")
            if not isinstance(old, str) or not old or not isinstance(new, str):
                raise ToolError("old 必须为非空字符串，new 必须为字符串")
            first = old_text.find(old)
            if first < 0:
                raise ToolError("未找到精确匹配。请重新 read，保留原始缩进和换行。")
            if old_text.find(old, first + 1) >= 0:
                raise ToolError("匹配不唯一。请增加 old 的上下文直到只出现一次。")
            new_text = old_text[:first] + new + old_text[first + len(old):]
        else:
            new_text = args.get("content")
            if not isinstance(new_text, str):
                raise ToolError("content 必须为字符串")
        if len(new_text.encode("utf-8")) > 2_000_000:
            raise ToolError("单次写入不能超过 2 MB")
        diff = "".join(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        return {"path": path, "before": old_text, "after": new_text, "diff": diff[:40000], "version": self.ws.version(path), "old_lines": len(old_text.splitlines()), "new_lines": len(new_text.splitlines())}

    def commit(self, prepared: dict) -> dict:
        target = self.ws.resolve(prepared["path"])
        if self.ws.version(prepared["path"]) != prepared["version"]:
            raise ToolError("文件在预览后发生变化，本次修改未写入。请重新读取并生成修改。")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pypilot-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(prepared["after"])
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {"path": prepared["path"], "old_lines": prepared["old_lines"], "new_lines": prepared["new_lines"], "message": "已原子写入", "diff": prepared["diff"]}

    @staticmethod
    def shell() -> tuple[list[str], str]:
        if os.name == "nt":
            candidates = [Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/bin/bash.exe"]
            for p in candidates:
                if p.is_file():
                    return [str(p), "--noprofile", "--norc", "-c"], "Git Bash"
            return ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand"], "PowerShell"
        return [shutil.which("bash") or "/bin/sh", "-c"], "bash"

    async def kill(self, process):
        if os.name == "nt":
            import win32job
            job = self.jobs.get(process.pid)
            if job:
                win32job.TerminateJobObject(job, 1)
            elif process.returncode is None:
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()

    async def bash(self, command: str, timeout: int) -> dict:
        if not isinstance(command, str) or not command.strip() or len(command) > 12000:
            raise ToolError("command 必须是非空命令，最多 12000 字符")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 120:
            raise ToolError("timeout 必须为 1–120 秒")
        shell, label = self.shell()
        if label == "PowerShell":
            script = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); " + command + "; if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }"
            command = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ("API_KEY", "SECRET", "TOKEN", "PASSWORD"))}
        env["PYTHONIOENCODING"] = "utf-8"
        from .config import assets_dir
        local_python = self.ws.root / (".venv/Scripts" if os.name == "nt" else ".venv/bin")
        bundled_python = assets_dir() / "runtime/python"
        interpreter_dir = local_python if (local_python / ("python.exe" if os.name == "nt" else "python")).exists() else bundled_python if bundled_python.exists() else Path(sys.executable).parent
        env["PATH"] = str(interpreter_dir) + os.pathsep + str(interpreter_dir / "Scripts") + os.pathsep + env.get("PATH", "")
        env.pop("PYTHONPATH", None)
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = await asyncio.create_subprocess_exec(*shell, command, cwd=self.ws.root, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **flags)
        self.processes.add(process)
        if os.name == "nt":
            import win32api
            import win32job
            job = win32job.CreateJobObject(None, "")
            limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
            limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
            handle = win32api.OpenProcess(0x0100 | 0x0001, False, process.pid)
            try:
                win32job.AssignProcessToJobObject(job, handle)
                self.jobs[process.pid] = job
            except Exception:
                process.kill()
                job.Close()
                self.processes.discard(process)
                await process.wait()
                raise ToolError("无法建立命令进程隔离，已拒绝执行")
            finally:
                handle.Close()
        chunks = {"stdout": bytearray(), "stderr": bytearray()}
        sizes = {"stdout": 0, "stderr": 0}

        async def drain(stream, name):
            while chunk := await stream.read(4096):
                sizes[name] += len(chunk)
                free = max(0, 16000 - len(chunks[name]))
                chunks[name].extend(chunk[:free])

        readers = [asyncio.create_task(drain(process.stdout, "stdout")), asyncio.create_task(drain(process.stderr, "stderr"))]
        # Include pipe draining in the deadline: a child can keep inherited
        # handles open even after its shell parent has already exited.
        completion = asyncio.gather(process.wait(), *readers)
        timed_out = False
        try:
            try:
                await asyncio.wait_for(asyncio.shield(completion), timeout)
            except asyncio.TimeoutError:
                timed_out = True
                await self.kill(process)
                await asyncio.wait_for(completion, 5)
        except asyncio.CancelledError:
            await asyncio.shield(self.kill(process))
            for task in readers:
                task.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            await asyncio.gather(completion, return_exceptions=True)
            raise
        finally:
            self.processes.discard(process)
            job = self.jobs.pop(process.pid, None)
            if job:
                job.Close()
        result = {k: v.decode("utf-8", errors="replace") for k, v in chunks.items()}
        result.update(exit_code=process.returncode, timed_out=timed_out, truncated=any(n > 16000 for n in sizes.values()), output_bytes=sizes, shell=label)
        return result

    async def execute(self, name, args):
        if name == "read":
            return self.read(**args)
        if name in {"write", "edit"}:
            return self.commit(self.prepare(name, args))
        if name == "bash":
            return await self.bash(**args)
        raise ToolError(f"未知工具：{name}")
