"""Workspace filesystem boundary and a small Python-only project map."""
from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path

IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build", ".idea"}
SECRET_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json", "settings.json"}


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("工作区目录不存在")

    def resolve(self, path: str, *, allow_root=False) -> Path:
        if not isinstance(path, str) or not path or "\x00" in path:
            raise ValueError("请提供有效的工作区相对路径")
        if Path(path).is_absolute() or Path(path).drive or (os.name == "nt" and ":" in path):
            raise ValueError("必须使用工作区相对路径，不支持驱动器或备用数据流")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root) or (target == self.root and not allow_root):
            raise ValueError("路径越界：只允许访问当前工作区中的文件")
        if any(p.lower() in IGNORED for p in target.relative_to(self.root).parts):
            raise ValueError("此目录已从工作区访问范围排除")
        name = target.name.lower()
        if name in SECRET_NAMES or (name.startswith(".env.") and name != ".env.example") or target.suffix.lower() in {".pem", ".key"}:
            raise ValueError("密钥或配置文件不会提供给模型")
        return target

    @staticmethod
    def decode(data: bytes) -> str:
        if b"\x00" in data[:4096]:
            raise ValueError("这是二进制文件，不能作为文本编辑")
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("当前版本只编辑 UTF-8 文本，请先转换编码")

    def text(self, path: str, max_bytes=2_000_000) -> str:
        p = self.resolve(path)
        if not p.is_file():
            raise ValueError(f"文件不存在：{path}")
        if p.stat().st_size > max_bytes:
            raise ValueError("文件过大，请通过 read 分页读取")
        return self.decode(p.read_bytes())

    def files(self, cap=2000) -> list[dict]:
        result = []
        for parent, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d.lower() not in IGNORED and not (Path(parent) / d).is_symlink())
            for name in sorted(files):
                p = Path(parent) / name
                rel = p.relative_to(self.root).as_posix()
                try:
                    self.resolve(rel)
                    if p.is_symlink():
                        continue
                    result.append({"path": rel, "size": p.stat().st_size, "python": p.suffix == ".py"})
                    if len(result) >= cap:
                        return result
                except (ValueError, OSError):
                    continue
        return result

    def project_map(self, query="", cap=16000) -> dict:
        files = self.files()
        words = set(re.findall(r"[\w]+", query.lower()))
        records, errors = [], []
        for f in files:
            if not f["python"] or f["size"] > 300000:
                continue
            try:
                content = self.text(f["path"])
                module = ast.parse(content, filename=f["path"])
                lines = [f["path"]]
                symbols, imports = [], []
                for node in module.body:
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports.append(ast.unparse(node))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        signature = content.splitlines()[node.lineno - 1].strip()
                        lines.append(f"  L{node.lineno}: {signature[:200]}")
                        symbols.append({"name": node.name, "line": node.lineno, "kind": "class" if isinstance(node, ast.ClassDef) else "function"})
                        if isinstance(node, ast.ClassDef):
                            for child in node.body:
                                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    lines.append(f"    L{child.lineno}: {content.splitlines()[child.lineno - 1].strip()[:160]}")
                if imports:
                    lines.append("  imports: " + "; ".join(imports)[:600])
                score = sum(3 for w in words if w in f["path"].lower()) + sum(1 for w in words if w in " ".join(lines).lower())
                records.append({"path": f["path"], "symbols": symbols, "imports": imports, "summary": "\n".join(lines), "score": score})
            except (ValueError, SyntaxError, OSError) as e:
                errors.append({"path": f["path"], "error": str(e)[:180]})
        records.sort(key=lambda r: (-r["score"], r["path"]))
        summary = "\n\n".join(r["summary"] for r in records)
        return {"files": files, "modules": records, "errors": errors, "summary": summary[:cap], "truncated": len(summary) > cap}

    def search(self, query: str, limit=80) -> list[dict]:
        if not query.strip():
            return []
        hits = []
        for f in self.files():
            if f["size"] > 500000:
                continue
            try:
                for n, line in enumerate(self.text(f["path"]).splitlines(), 1):
                    if query.lower() in line.lower():
                        hits.append({"path": f["path"], "line": n, "text": line[:260]})
                        if len(hits) >= limit:
                            return hits
            except (ValueError, OSError):
                continue
        return hits

    def version(self, path: str) -> str:
        p = self.resolve(path)
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"

