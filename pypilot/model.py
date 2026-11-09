"""OpenAI-compatible streaming client; network and credentials stay in Python."""
from __future__ import annotations
import json
from urllib.parse import urlparse
import httpx


class ModelError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, settings):
        self.settings = settings

    async def stream(self, messages, schemas=None, *, completion=False):
        cfg = self.settings.values
        base = cfg["base_url"].rstrip("/")
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ModelError("模型地址必须是有效的 http/https API 地址，不能在地址中嵌入密钥")
        model = (cfg.get("completion_model") if completion else "") or cfg["model"]
        if not model:
            raise ModelError("请先在模型设置中填写模型名称")
        headers = {"Content-Type": "application/json"}
        if self.settings.key():
            headers["Authorization"] = "Bearer " + self.settings.key()
        payload = {"model": model, "messages": messages, "stream": True, "max_tokens": 384 if completion else 4096}
        if schemas:
            payload.update(tools=schemas, tool_choice="auto")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15), trust_env=True) as client:
                async with client.stream("POST", base + "/chat/completions", headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        hint = {401: "API Key 无效或未配置", 403: "模型服务拒绝访问", 404: "检查 API 地址和模型名", 429: "额度不足或请求过于频繁"}.get(response.status_code, "请检查服务状态及模型是否支持工具调用")
                        raise ModelError(f"模型服务返回 HTTP {response.status_code}：{hint}")
                    calls = {}
                    text = ""
                    finished = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            finished = True
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if data.get("error"):
                            raise ModelError("模型服务在输出过程中返回错误，请检查服务端日志与额度")
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        if delta.get("content"):
                            text += delta["content"]
                            yield {"type": "token", "delta": delta["content"]}
                        for item in delta.get("tool_calls", []):
                            current = calls.setdefault(item.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            if item.get("id"):
                                current["id"] = item["id"]
                            for field in ("name", "arguments"):
                                current["function"][field] += item.get("function", {}).get(field, "")
                        if choice.get("finish_reason") == "length":
                            raise ModelError("模型输出达到长度上限，当前回答未完整生成，请缩小任务")
                        if choice.get("finish_reason"):
                            finished = True
                    if not finished:
                        raise ModelError("模型流意外断开，未执行不完整的工具请求，请重试")
                    message = {"role": "assistant", "content": text or None}
                    if calls:
                        message["tool_calls"] = [calls[k] for k in sorted(calls)]
                    if not text and not calls:
                        raise ModelError("模型没有返回内容，请检查接口是否支持流式 chat/completions")
                    yield {"type": "message", "message": message}
        except httpx.TimeoutException:
            raise ModelError("模型请求超时，请检查网络或更换模型")
        except httpx.HTTPError:
            raise ModelError("无法连接模型服务，请检查 API 地址、网络和证书")

    async def complete(self, prefix, suffix, path, context):
        messages = [
            {"role": "system", "content": "你是 Python 代码补全器。只输出应插入光标的少量代码，不输出 Markdown 或解释，不重复前后缀。保留缩进，不更改已有代码。"},
            {"role": "user", "content": f"文件：{path}\n相关 Python 符号：\n{context[:3000]}\n<prefix>\n{prefix[-6000:]}\n</prefix>\n<suffix>\n{suffix[:2000]}\n</suffix>\n输出光标位置的插入文本："},
        ]
        text = ""
        async for event in self.stream(messages, completion=True):
            if event["type"] == "token":
                text += event["delta"]
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        # Some providers echo a suffix. Keep the existing suffix intact.
        for n in range(min(len(suffix), len(text), 100), 0, -1):
            if text.endswith(suffix[:n]):
                text = text[:-n]
                break
        return text[:2000]

