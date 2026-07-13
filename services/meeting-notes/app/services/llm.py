"""LLM 客户端 - 支持 GLM / minimax / oMLX 三供应商
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用错误（不可重试：HTTP 4xx 业务错误 / JSON 解析失败）"""


class LLMNetworkError(LLMError):
    """LLM 网络错误（可重试：连接超时 / 5xx 服务端临时故障）"""


class LLMClient:
    """LLM 客户端（统一接口，支持 GLM / minimax / oMLX）"""

    def __init__(self, provider: str = "glm"):
        """Args:
        provider: "glm" / "minimax" / "omlx"
        """
        self.provider = provider
        if provider == "glm":
            self.api_key = settings.glm_api_key
            self.base_url = settings.glm_base_url
            self.model = settings.glm_model
        elif provider == "minimax":
            self.api_key = settings.minimax_api_key
            self.base_url = settings.minimax_base_url
            self.model = settings.minimax_model
        elif provider == "omlx":
            self.api_key = settings.omlx_api_key
            self.base_url = settings.omlx_base_url
            self.model = settings.omlx_model
        else:
            raise ValueError(f"Unknown provider: {provider}")

        if not self.api_key:
            raise ValueError(f"API key not configured for provider: {provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(LLMNetworkError),
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        """聊天调用

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度
            max_tokens: 最大 token
            response_format: 响应格式（如 {"type": "json_object"}）

        Returns:
            响应内容
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # oMLX 不一定支持 response_format，跳过
        if response_format and self.provider != "omlx":
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as e:
                # 网络层错误（连接/超时）→ 可重试
                raise LLMNetworkError(f"Network error: {e}") from e
            # 5xx 服务端临时故障 → 可重试；4xx 业务错误 → 不重试
            if resp.status_code >= 500:
                raise LLMNetworkError(
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
            if resp.status_code != 200:
                raise LLMError(
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 3000,
    ) -> Any:
        """JSON 响应调用"""
        # 添加格式约束提示
        if not any("json" in m.get("content", "").lower() for m in messages):
            messages = messages + [
                {
                    "role": "system",
                    "content": "请用严格的 JSON 格式输出，不要包含任何额外说明文字。",
                }
            ]

        # oMLX 不支持 response_format
        response_format = (
            {"type": "json_object"} if self.provider != "omlx" else None
        )

        response = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        # 提取 JSON（兼容 ```json ... ``` / ``` ... ``` / 单行 / 无闭合 等格式）
        response = response.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if fenced:
            response = fenced.group(1).strip()
        elif response.startswith("```"):
            # 仅有开头 ``` 无闭合，剥去首行
            response = response.split("\n", 1)[-1].strip()

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nResponse: {response[:500]}")
            raise LLMError(f"Invalid JSON response: {e}")


# 会议纪要专用 Prompt
MEETING_SUMMARY_PROMPT = """你是一位专业的会议记录员，擅长将会议录音转写文本整理成结构化的会议纪要。

请基于以下会议转写文本，输出严格的 JSON 格式（不要任何额外说明）：

```json
{{
  "summary": "（200-400字）会议整体摘要，包含会议主题、主要结论和关键进展",
  "key_points": [
    "要点1",
    "要点2",
    "..."
  ],
  "decisions": [
    "决策1（含决策人和生效时间）",
    "..."
  ],
  "action_items": [
    {{
      "task": "具体任务描述",
      "owner": "负责人姓名（从参会人中推断）",
      "deadline": "YYYY-MM-DD（若明确）",
      "priority": "P0/P1/P2"
    }}
  ],
  "attendees": ["参会人1", "参会人2"]
}}
```

要求：
1. summary 要简洁精炼，抓重点
2. key_points 列出 3-7 条核心要点
3. decisions 列出所有明确决策（含决策人）
4. action_items 必须具体可执行，含负责人和截止日期
5. 若信息缺失，对应字段填空数组或空字符串

【会议转写】
{transcript}
"""


async def generate_meeting_summary(
    transcript: str,
    provider: str = "glm",
) -> Dict[str, Any]:
    """生成会议纪要结构化摘要

    Args:
        transcript: 转写文本
        provider: LLM 提供商 ("glm" / "minimax" / "omlx")

    Returns:
        摘要 dict: {summary, key_points, decisions, action_items, attendees}
    """
    client = LLMClient(provider=provider)
    prompt = MEETING_SUMMARY_PROMPT.format(transcript=transcript)

    result = await client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=3000,
    )

    # 确保必要字段存在
    defaults = {
        "summary": "",
        "key_points": [],
        "decisions": [],
        "action_items": [],
        "attendees": [],
    }
    for k, v in defaults.items():
        if k not in result:
            result[k] = v

    return result


# 全局实例
_llm_client: Optional[LLMClient] = None


def get_llm_client(provider: str = "glm") -> LLMClient:
    global _llm_client
    if _llm_client is None or _llm_client.provider != provider:
        _llm_client = LLMClient(provider=provider)
    return _llm_client


def list_providers() -> List[Dict[str, Any]]:
    """列出所有可用的 LLM provider 及其配置状态"""
    providers = [
        {
            "name": "glm",
            "display_name": "智谱 GLM (云)",
            "configured": bool(settings.glm_api_key),
            "model": settings.glm_model,
            "base_url": settings.glm_base_url,
            "supports_json_mode": True,
        },
        {
            "name": "minimax",
            "display_name": "minimax (云)",
            "configured": bool(settings.minimax_api_key),
            "model": settings.minimax_model,
            "base_url": settings.minimax_base_url,
            "supports_json_mode": True,
        },
        {
            "name": "omlx",
            "display_name": "oMLX (本地 MLX)",
            "configured": settings.omlx_enabled and bool(settings.omlx_api_key),
            "model": settings.omlx_model,
            "base_url": settings.omlx_base_url,
            "supports_json_mode": False,
            "note": "OpenAI 兼容协议，跑 Apple Silicon 优化的 MLX 模型",
        },
    ]
    return providers