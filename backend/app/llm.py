from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from app import config
from app.prompts.common import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_llm = None
_executor = ThreadPoolExecutor(max_workers=1)

LLM_TIMEOUT = config.LLM_TIMEOUT
JSON_EXTRACT_RETRIES = 2


class LLMError(Exception):
    """LLM 추론 실패 시 발생하는 예외."""
    pass


def load_model():
    global _llm
    if _llm is not None:
        return

    from llama_cpp import Llama

    logger.info("모델 로딩 시작: %s", config.MODEL_PATH)
    _llm = Llama(
        model_path=config.MODEL_PATH,
        n_ctx=config.LLM_CONTEXT_SIZE,
        n_threads=config.LLM_THREADS,
        verbose=False,
    )
    logger.info("모델 로딩 완료")


def is_loaded() -> bool:
    return _llm is not None


def generate(prompt: str, system: str | None = None) -> str:
    """동기 추론. 타임아웃 적용."""
    _ensure_loaded()

    messages = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    def _run():
        return _llm.create_chat_completion(
            messages=messages,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
        )

    try:
        future = _executor.submit(_run)
        response = future.result(timeout=LLM_TIMEOUT)
        content = response["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise LLMError("LLM이 빈 응답을 반환했습니다.")
        return _strip_think(content).strip()
    except FuturesTimeout:
        raise LLMError(f"LLM 추론 타임아웃 ({LLM_TIMEOUT}초 초과)")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"LLM 추론 실패: {e}") from e


def generate_safe(prompt: str, system: str | None = None, fallback: str = "") -> str:
    """추론 실패 시 fallback 문자열을 반환한다. 예외를 전파하지 않는다."""
    try:
        return generate(prompt, system=system)
    except LLMError as e:
        logger.error("LLM 추론 실패 (fallback 사용): %s", e)
        return fallback


def generate_stream(prompt: str, system: str | None = None) -> Iterator[str]:
    """스트리밍 추론. <think> 블록을 건너뛰고 토큰 간 타임아웃을 적용한다."""
    _ensure_loaded()
    import time

    messages = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    last_token_time = time.monotonic()
    in_think = False
    think_buf = ""
    try:
        for chunk in _llm.create_chat_completion(
            messages=messages,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            stream=True,
        ):
            now = time.monotonic()
            if now - last_token_time > LLM_TIMEOUT:
                raise LLMError(f"스트리밍 타임아웃 ({LLM_TIMEOUT}초 간 토큰 없음)")
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content", "")
            if not token:
                continue

            last_token_time = now
            think_buf += token

            # <think> 블록 감지 및 스킵
            if not in_think:
                if "<think>" in think_buf:
                    in_think = True
                    think_buf = think_buf[think_buf.index("<think>") + len("<think>"):]
                else:
                    yield think_buf
                    think_buf = ""
            if in_think:
                if "</think>" in think_buf:
                    in_think = False
                    remainder = think_buf[think_buf.index("</think>") + len("</think>"):]
                    think_buf = ""
                    if remainder:
                        yield remainder
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"스트리밍 추론 실패: {e}") from e


def extract_json(prompt: str, system: str | None = None, retries: int = JSON_EXTRACT_RETRIES) -> dict | None:
    """LLM 응답에서 JSON 객체를 추출한다. 실패 시 재시도한다."""
    for attempt in range(1, retries + 1):
        try:
            raw = generate(prompt, system=system)
        except LLMError as e:
            logger.warning("JSON 추출 시도 %d 실패 (LLM 에러): %s", attempt, e)
            continue

        parsed = _try_parse_json(raw)
        if parsed is not None:
            return parsed
        logger.warning("JSON 추출 시도 %d 실패 (파싱 에러): %s", attempt, raw[:200])

    return None


def _try_parse_json(text: str) -> dict | None:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None


def _strip_think(text: str) -> str:
    """Qwen3의 <think>...</think> 내부 추론 블록을 제거한다."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _ensure_loaded():
    if _llm is None:
        raise LLMError("LLM이 로드되지 않았습니다. 모델 파일을 확인하세요.")
