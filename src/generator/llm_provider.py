from dataclasses import dataclass
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class LLMGenerationResult:
    text: str
    provider_name: str
    status: str


class StubLLMProvider:
    name = "stub"

    def generate(self, prompt: str) -> LLMGenerationResult:
        return LLMGenerationResult(
            text="",
            provider_name=self.name,
            status="stub_no_external_call",
        )


class ZhipuGLMProvider:
    name = "zhipu-glm-4.5-air"
    endpoint = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    model = "glm-4.5-air"
    max_retries = 3
    timeout_seconds = 90

    def generate(self, prompt: str) -> LLMGenerationResult:
        api_key = os.getenv("ZHIPUAI_API_KEY", "").strip()
        if not api_key:
            return LLMGenerationResult(
                text="",
                provider_name=self.name,
                status="missing_api_key",
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个严谨的思政教育问答生成智能体。"
                        "必须依据用户提供的证据回答，不能编造事实、来源或页码。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "top_p": 0.8,
            "max_tokens": 900,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        data = None
        for attempt in range(self.max_retries):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeEncodeError):
                if attempt == self.max_retries - 1:
                    return LLMGenerationResult(
                        text="",
                        provider_name=self.name,
                        status="api_error",
                    )
                time.sleep(2 * (attempt + 1))

        choices = (data or {}).get("choices") or []
        if not choices:
            return LLMGenerationResult(
                text="",
                provider_name=self.name,
                status="empty_response",
            )

        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        status = "success" if text else "empty_response"
        return LLMGenerationResult(
            text=text,
            provider_name=self.name,
            status=status,
        )


def get_llm_provider(provider_name: str):
    if provider_name in {"zhipu", "glm", "glm-4.5-air", "zhipu-glm-4.5-air"}:
        return ZhipuGLMProvider()
    return StubLLMProvider()
