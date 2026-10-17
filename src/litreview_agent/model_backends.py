"""模型后端适配器：Anthropic 兼容 Messages API。

- 凭证只从环境变量读（ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / 模型名），
  不写入任何文件或日志；
- 记录每次调用的 model、参数、usage 到调用方提供的 logger；
- 工具循环支持 Anthropic tools 协议（tool_use / tool_result）；
- 失败如实抛出，不虚构响应。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

PROMPT_VERSION = "g2-v1"


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, u: dict[str, Any] | None) -> None:
        if not u:
            return
        self.calls += 1
        self.input_tokens += u.get("input_tokens") or 0
        self.output_tokens += u.get("output_tokens") or 0


@dataclass
class ModelResult:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class ModelBackendError(Exception):
    pass


class AnthropicBackend:
    """最小 Anthropic 兼容客户端（httpx，无 SDK 依赖）。"""

    def __init__(self, logger: Optional[Callable[[dict[str, Any]], None]] = None,
                 max_tokens: int = 4096, timeout: float = 240.0):
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
        token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        self.api_key = token
        # 模型选择：显式覆盖 > HAIKU 变量（实测本端点仅该变量指向的模型可用）
        # > SONNET 变量。端点实际服务的模型以响应中的 model 字段为准并记录。
        self.model = (os.environ.get("LITREVIEW_MODEL")
                      or os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
                      or os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL") or "")
        if not (self.base_url and self.api_key and self.model):
            raise ModelBackendError(
                "模型后端未配置：需要 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / "
                "LITREVIEW_MODEL（或 ANTHROPIC_DEFAULT_HAIKU/SONNET_MODEL）环境变量")
        self.max_tokens = max_tokens
        self.usage = Usage()
        self._logger = logger
        self._client = httpx.Client(
            timeout=timeout,
            headers={"x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})

    def complete(self, messages: list[dict[str, Any]],
                 system: Optional[str] = None,
                 tools: Optional[list[dict[str, Any]]] = None,
                 max_tokens: Optional[int] = None) -> ModelResult:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        r = self._client.post(f"{self.base_url}/v1/messages", json=body)
        if r.status_code != 200:
            raise ModelBackendError(
                f"模型调用失败 HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        self.usage.add(data.get("usage"))
        if self._logger:
            self._logger({"kind": "model_result", "model": data.get("model"),
                          "usage": data.get("usage"),
                          "stop_reason": data.get("stop_reason"),
                          "prompt_version": PROMPT_VERSION})
        result = ModelResult(stop_reason=data.get("stop_reason") or "",
                             raw=data)
        for block in data.get("content", []):
            if block.get("type") == "text":
                result.text += block.get("text", "")
            elif block.get("type") == "tool_use":
                result.tool_calls.append({"id": block["id"],
                                          "name": block["name"],
                                          "input": block.get("input", {})})
        return result

    def tool_loop(self, system: str, user_message: str,
                  tools: list[dict[str, Any]],
                  executor: Callable[[str, dict[str, Any]], str],
                  max_steps: int = 12) -> tuple[str, list[dict[str, Any]]]:
        """工具调用循环：executor(name, input) -> tool_result 文本。

        返回 (最终文本回复, 完整消息历史)。单回合步数受 max_steps 约束。
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        history = list(messages)
        for step in range(max_steps):
            result = self.complete(messages=messages, system=system, tools=tools)
            if not result.tool_calls:
                return result.text, history
            # 组装 tool_use 内容块并执行
            content: list[dict[str, Any]] = []
            if result.text:
                content.append({"type": "text", "text": result.text})
            tool_results = []
            for call in result.tool_calls:
                try:
                    out = executor(call["name"], call["input"])
                    status = "ok"
                except Exception as e:  # noqa: BLE001 — 工具失败也要回给模型
                    out, status = f"工具执行错误: {e}", "error"
                if self._logger:
                    self._logger({"kind": "tool_call", "tool": call["name"],
                                  "input_summary": str(call["input"])[:200],
                                  "result_summary": str(out)[:300],
                                  "status": status, "step": step})
                content.append({"type": "tool_use", "id": call["id"],
                                "name": call["name"], "input": call["input"]})
                tool_results.append({"type": "tool_result",
                                     "tool_use_id": call["id"],
                                     "content": str(out)[:15000]})
            messages = [{"role": "assistant", "content": content},
                        {"role": "user", "content": tool_results}]
            history.extend(messages)
        return "（达到单回合最大工具步数，流程保存状态后结束）", history
