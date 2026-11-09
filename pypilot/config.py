"""User configuration. Keys never enter frontend state, logs, or the project."""
from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("PYPILOT_DATA_DIR")
    root = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "PyPilot"
    root.mkdir(parents=True, exist_ok=True)
    return root


def assets_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def python_command() -> str:
    bundled = assets_dir() / "runtime/python/python.exe"
    return str(bundled) if bundled.is_file() else sys.executable


def _crypt(data: bytes, decrypt: bool = False) -> bytes:
    """Windows DPAPI binds saved credentials to the current Windows account."""
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    dst = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    fn.restype = ctypes.c_int
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
        raise OSError("无法使用 Windows 凭据加密")
    try:
        return ctypes.string_at(dst.data, dst.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
        ctypes.windll.kernel32.LocalFree(dst.data)


class Settings:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "settings.json"
        self.values = {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "completion_model": "", "max_steps": 16, "timeout": 180, "max_context_chars": 60000, "workspace": "", "mcp_servers": []}
        if self.path.exists():
            self.values.update(json.loads(self.path.read_text("utf-8")))
        self.session_key = ""
        self.key_storage = "Windows DPAPI" if sys.platform == "win32" else "本次会话"
        self.values["base_url"] = os.environ.get("PYPILOT_BASE_URL") or self.values["base_url"]
        self.values["model"] = os.environ.get("PYPILOT_MODEL") or self.values["model"]

    def key(self) -> str:
        if os.environ.get("PYPILOT_API_KEY"):
            return os.environ["PYPILOT_API_KEY"]
        if self.session_key:
            return self.session_key
        encoded = self.values.get("encrypted_key")
        if encoded and sys.platform == "win32":
            try:
                return _crypt(base64.b64decode(encoded), True).decode()
            except (OSError, ValueError):
                return ""
        return ""

    def public(self) -> dict:
        result = {k: v for k, v in self.values.items() if k != "encrypted_key"}
        result["has_key"] = bool(self.key())
        result["key_storage"] = self.key_storage
        return result

    def update(self, values: dict):
        allowed = {"base_url", "model", "completion_model", "max_steps", "timeout", "max_context_chars", "workspace", "mcp_servers"}
        for name in allowed:
            if name in values:
                self.values[name] = values[name]
        self.values["max_steps"] = max(1, min(40, int(self.values["max_steps"])))
        self.values["timeout"] = max(10, min(600, int(self.values["timeout"])))
        self.values["max_context_chars"] = max(8000, min(120000, int(self.values["max_context_chars"])))
        if values.get("clear_key"):
            self.session_key = ""
            self.values.pop("encrypted_key", None)
        if values.get("api_key"):
            self.session_key = values["api_key"].strip()
            if sys.platform == "win32":
                try:
                    self.values["encrypted_key"] = base64.b64encode(_crypt(self.session_key.encode())).decode()
                    self.key_storage = "Windows DPAPI"
                except OSError:
                    # Restricted Windows profiles may not have a DPAPI key store.
                    # Keep the key in RAM only; never fall back to plaintext.
                    self.values.pop("encrypted_key", None)
                    self.key_storage = "仅本次会话（系统凭据加密不可用）"
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.path)

