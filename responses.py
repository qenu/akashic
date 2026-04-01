import json
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import grpc
from pydantic import BaseModel, Field

from xai_sdk import Client
from xai_sdk.chat import assistant, system, user

from app_logger import AppLogger

log = AppLogger.get_logger("api")


class GameplayResponse(BaseModel):
    narrative: list[str]
    options: list[str] = Field(min_length=4, max_length=4)
    summary: list[str]
    changes: list[dict[str, Any]]


class APIError(Exception):
    """Raised when the API request fails or returns an invalid response."""


_TRANSIENT_MARKERS = (
    "502",
    "503",
    "unavailable",
    "deadline exceeded",
    "resource exhausted",
)


def _is_transient(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


_THINK_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks, logging their content first."""
    def _log_and_remove(m: re.Match) -> str:
            thinking = m.group(1).strip()
            if thinking:
                log.info("API reasoning — {}", thinking)
            return ""

    return _THINK_RE.sub(_log_and_remove, text).strip()


def _log_response(logger: Any, response: Any, model: str, raw: str, log_raw: bool) -> None:
    """Log API response: always log stats + summary/changes; full raw only when log_raw_io=True."""
    usage = response.usage
    base = (
        "API response — id: {} | model: {} | created: {} | finish: {} | "
        "usage: prompt={} (text={}, cached={}, image={}) completion={} reasoning={} total={} sources={} tools={}"
    )
    args = [
        response.id, model, response.created, response.finish_reason,
        usage.prompt_tokens, usage.prompt_text_tokens, usage.cached_prompt_text_tokens,
        usage.prompt_image_tokens, usage.completion_tokens, usage.reasoning_tokens,
        usage.total_tokens, usage.num_sources_used, usage.server_side_tools_used,
    ]
    if log_raw:
        logger.info(base + " | raw: {}", *args, raw)
        return

    # Parse and log only summary + changes
    try:
        payload = json.loads(raw)
        if "世界觀" in payload:
            # World-init response — no summary field
            logger.info(base + " | [world-init]", *args)
            return
        summary = payload.get("summary") or []
        changes = payload.get("changes") or []
        summary_str = " ".join(summary) if isinstance(summary, list) else str(summary)
        logger.info(base + " | summary: {} | changes: {}", *args, summary_str,
                    json.dumps(changes, ensure_ascii=False))
    except Exception:
        logger.info(base + " | [unparseable]", *args)



@dataclass
class APIConfig:
    base_url: str
    api_key: str
    model: str = "grok-3-latest"
    reasoning_model: str = "grok-3-mini"
    temperature: float = 1.0
    max_tokens: int = 4096
    store: bool = False
    timeout_seconds: float = 30.0
    log_raw_io: bool = False


class ResponseClient:
    """xAI SDK client for Grok chat-completion calls."""

    def __init__(self, config: APIConfig) -> None:
        self._config = config

    @staticmethod
    def _to_sdk_messages(messages: list[dict[str, str]]) -> list:
        sdk_messages = []
        for message in messages:
            role = message.get("role", "").strip().lower()
            content = message.get("content", "")

            if role == "system":
                sdk_messages.append(system(content))
            elif role == "assistant":
                sdk_messages.append(assistant(content))
            else:
                sdk_messages.append(user(content))
        return sdk_messages

    def _normalized_api_host(self) -> str:
        value = self._config.base_url.strip()
        if not value:
            return "api.x.ai"

        # Accept either host-only or URL forms, e.g. "api.x.ai" or "https://api.x.ai/v1".
        if "://" in value:
            parsed = urlparse(value)
            return parsed.netloc or parsed.path.strip("/") or "api.x.ai"

        return value.strip("/")

    def _log_input(self, messages: list[dict[str, str]]) -> None:
        if self._config.log_raw_io:
            log.info("API input — {}", json.dumps(messages, ensure_ascii=False))

    def _log_output(self, content: str) -> None:
        if self._config.log_raw_io:
            log.info("API output — {}", content)

    def send_messages(
        self, messages: list[dict[str, str]], *, reasoning: bool = False, use_schema: bool = True
    ) -> str:
        self._log_input(messages)
        sdk_messages = self._to_sdk_messages(messages)

        model = (
            (self._config.reasoning_model or self._config.model)
            if reasoning
            else self._config.model
        )

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            client = Client(
                api_key=self._config.api_key,
                api_host=self._normalized_api_host(),
                timeout=self._config.timeout_seconds,
            )
            try:
                chat = client.chat.create(
                    model=model,
                    messages=sdk_messages,
                    temperature=1.0 if reasoning else self._config.temperature,
                    max_tokens=self._config.max_tokens,
                    store_messages=self._config.store,
                    response_format=GameplayResponse if (use_schema and not reasoning) else ("json_object" if reasoning else None),
                    reasoning_effort="high" if reasoning else None,
                )
                response = chat.sample()
                raw = (response.content or "").strip()
                content = _strip_thinking(raw).strip()
                _log_response(log, response, model, content, self._config.log_raw_io)
                if not content:
                    raise APIError("Unexpected API response format")
                if use_schema and not reasoning:
                    try:
                        json.loads(content)
                    except Exception:
                        if attempt < max_attempts:
                            log.warning(
                                "Response is not valid JSON (attempt {}/{}), retrying…",
                                attempt, max_attempts,
                            )
                            continue
                        raise APIError("Response is not valid JSON after all retries")
                return content
            except APIError:
                raise
            except Exception as exc:
                grpc_code = getattr(exc, 'code', None)
                code_str = f" [gRPC {grpc_code()}]" if callable(grpc_code) else ""
                if _is_transient(exc) and attempt < max_attempts:
                    delay = 2 ** (attempt - 1)  # 1s, 2s
                    log.warning(
                        "Transient API error (attempt {}/{}), retrying in {}s{}: {}",
                        attempt,
                        max_attempts,
                        delay,
                        code_str,
                        exc,
                    )
                    time.sleep(delay)
                    continue
                log.exception("API call failed{}" , code_str)
                raise APIError(str(exc)) from exc
            finally:
                client.close()

        raise APIError("All retry attempts exhausted")

    def send_chat(
        self, user_text: str, system_prompt: str = "You are a helpful assistant."
    ) -> str:
        return self.send_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ]
        )
