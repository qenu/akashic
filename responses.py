import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from xai_sdk import Client
from xai_sdk.chat import assistant, system, user
from app_logger import AppLogger


log = AppLogger.get_logger("api")


class APIError(Exception):
    """Raised when the API request fails or returns an invalid response."""


_TRANSIENT_MARKERS = ("502", "503", "unavailable", "deadline exceeded", "resource exhausted")

def _is_transient(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


@dataclass
class APIConfig:
    base_url: str
    api_key: str
    model: str = "grok-3-latest"
    reasoning_model: str = "grok-3-mini"
    store: bool = False
    timeout_seconds: float = 30.0


class ResponseClient:
    """xAI SDK client for Grok chat-completion calls."""

    def __init__(self, config: APIConfig) -> None:
        self._config = config
        self._prompt_alias_by_content = self._load_prompt_aliases()

    def _load_prompt_aliases(self) -> dict[str, str]:
        base_path = Path(__file__).parent / "core"
        aliases: dict[str, str] = {}

        for file_name in ("system.md", "init.md"):
            file_path = base_path / file_name
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8").strip()
            if content:
                aliases[content] = file_name

        return aliases

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

    def _messages_for_log(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content", ""))
            normalized_content = content.strip()
            alias = self._prompt_alias_by_content.get(normalized_content)

            if role == "system" and alias:
                sanitized.append({"role": role, "content": alias})
                continue

            sanitized.append({"role": role, "content": content})

        return sanitized

    def _normalized_api_host(self) -> str:
        value = self._config.base_url.strip()
        if not value:
            return "api.x.ai"

        # Accept either host-only or URL forms, e.g. "api.x.ai" or "https://api.x.ai/v1".
        if "://" in value:
            parsed = urlparse(value)
            return parsed.netloc or parsed.path.strip("/") or "api.x.ai"

        return value.strip("/")

    def send_messages(self, messages: list[dict[str, str]], *, reasoning: bool = False) -> str:
        log_safe_messages = self._messages_for_log(messages)
        log.info("API raw input (reasoning={}): {}", reasoning, json.dumps(log_safe_messages, ensure_ascii=False))
        sdk_messages = self._to_sdk_messages(messages)

        model = (self._config.reasoning_model or self._config.model) if reasoning else self._config.model

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
                    temperature=0.7,
                    store_messages=self._config.store,
                )
                response = chat.sample()
                content = (response.content or "").strip()
                log.info("API raw output: {}", content)
                if not content:
                    raise APIError("Unexpected API response format")
                return content
            except APIError:
                raise
            except Exception as exc:
                if _is_transient(exc) and attempt < max_attempts:
                    delay = 2 ** (attempt - 1)  # 1s, 2s
                    log.warning("Transient API error (attempt {}/{}), retrying in {}s: {}", attempt, max_attempts, delay, exc)
                    time.sleep(delay)
                    continue
                log.exception("API call failed")
                raise APIError(str(exc)) from exc
            finally:
                client.close()

        raise APIError("All retry attempts exhausted")

    def stream_messages(self, messages: list[dict[str, str]]) -> Iterator[str]:
        log_safe_messages = self._messages_for_log(messages)
        log.info("API stream input: {}", json.dumps(log_safe_messages, ensure_ascii=False))
        sdk_messages = self._to_sdk_messages(messages)

        client = Client(
            api_key=self._config.api_key,
            api_host=self._normalized_api_host(),
            timeout=self._config.timeout_seconds,
        )

        try:
            chat = client.chat.create(
                model=self._config.model,
                messages=sdk_messages,
                temperature=0.7,
                store_messages=self._config.store,
            )
            for _response, chunk in chat.stream():
                delta = chunk.content or ""
                if delta:
                    yield delta
        except Exception as exc:
            log.exception("API stream call failed")
            raise APIError(str(exc)) from exc
        finally:
            client.close()

    def send_chat(self, user_text: str, system_prompt: str = "You are a helpful assistant.") -> str:
        return self.send_messages([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ])
