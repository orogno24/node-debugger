from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app import llm
from app.intent import classify_intent
from app.llm import LLMError
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ContentBlock,
    ContentType,
    IntentType,
    YamlModification,
)
from app.prompts import pod_analysis, yaml_modify
from app.session import session_manager
from app.tools import helm, yaml_editor
from app.tools.pod_analyzer import analyze_pod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/chat")
async def chat(req: ChatRequest):
    intent = classify_intent(req.message)

    handler = _HANDLERS.get(intent, _handle_unknown)
    try:
        return await handler(req, intent)
    except LLMError as e:
        logger.error("LLM 오류: %s", e)
        return _text_response(f"LLM 처리 중 오류가 발생했습니다: {e}", intent)
    except Exception as e:
        logger.exception("처리 중 예상치 못한 오류")
        return _text_response(f"내부 오류가 발생했습니다. 다시 시도해주세요.\n오류: {e}", intent)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 스트리밍 엔드포인트. Pod 분석처럼 LLM 응답이 긴 경우 사용."""
    intent = classify_intent(req.message)

    if intent != IntentType.POD_ANALYZE:
        response = await chat(req)
        async def _wrap():
            yield f"data: {json.dumps(response.model_dump(), default=str, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_wrap(), media_type="text/event-stream")

    session = session_manager.get(req.session_id)
    pod_name, namespace = _extract_pod_ref(req.message, session.current_pod, session.current_namespace)

    if not pod_name:
        err = _text_response("분석할 Pod 이름을 알려주세요.", intent)
        async def _err():
            yield f"data: {json.dumps(err.model_dump(), default=str, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    session_manager.set_target_pod(req.session_id, pod_name, namespace)

    pod_data, classification, error = await asyncio.to_thread(analyze_pod, pod_name, namespace)
    if error:
        err = _text_response(f"Pod 조회 실패: {error}", intent)
        async def _err2():
            yield f"data: {json.dumps(err.model_dump(), default=str, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_err2(), media_type="text/event-stream")

    prompt = pod_analysis.build_pod_analysis_prompt(pod_data, classification)

    async def _stream():
        try:
            stream_iter = await asyncio.to_thread(lambda: list(llm.generate_stream(prompt)))
            for token in stream_iter:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except LLMError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        evidence = {
            "issue_type": classification.issue_type.value,
            "confidence": classification.confidence.value,
            "affected_container": classification.affected_container,
            **classification.evidence,
        }
        yield f"data: {json.dumps({'evidence': evidence}, ensure_ascii=False)}\n\n"
        if classification.relevant_logs:
            yield f"data: {json.dumps({'logs': classification.relevant_logs}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/session/{session_id}")
async def get_session(session_id: str = "default"):
    return session_manager.get(session_id)


# --- Intent Handlers ---


async def _handle_pod_analyze(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)
    pod_name, namespace = _extract_pod_ref(req.message, session.current_pod, session.current_namespace)

    if not pod_name:
        return _text_response("분석할 Pod 이름을 알려주세요. 예: 'backend-api pod 상태 확인해줘'", intent)

    session_manager.set_target_pod(req.session_id, pod_name, namespace)

    pod_data, classification, error = await asyncio.to_thread(analyze_pod, pod_name, namespace)

    if error:
        return _text_response(f"Pod 조회 실패: {error}", intent)

    prompt = pod_analysis.build_pod_analysis_prompt(pod_data, classification)
    analysis = await asyncio.to_thread(llm.generate, prompt)

    contents = [ContentBlock(type=ContentType.TEXT, body=analysis)]
    if classification.relevant_logs:
        contents.append(ContentBlock(type=ContentType.CODE, body=classification.relevant_logs, language="log"))

    return ChatResponse(contents=contents, intent=intent)


async def _handle_helm_values_get(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)
    release, namespace = _extract_release_ref(req.message, session.current_release, session.current_namespace)

    if not release:
        return _text_response("릴리스 이름을 알려주세요. 예: 'frontend values 보여줘'", intent)

    session_manager.set_target_release(req.session_id, release, namespace)

    result = await helm.get_values(release, namespace)
    if not result.success:
        return _text_response(f"Helm values 조회 실패: {result.error}", intent)

    session_manager.store_original_values(req.session_id, result.data)

    return ChatResponse(
        contents=[
            ContentBlock(type=ContentType.TEXT, body=f"`{release}` 릴리스의 현재 values입니다."),
            ContentBlock(type=ContentType.YAML, body=result.data),
        ],
        intent=intent,
    )


async def _handle_yaml_modify(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)
    source = session.modified_values or session.original_values

    if not source:
        return _text_response("먼저 Helm values를 조회해주세요. 예: 'frontend values 보여줘'", intent)

    data = yaml_editor.load_yaml(source)
    flat_keys = _flatten_keys(data)

    prompt = yaml_modify.build_field_extraction_prompt(req.message, flat_keys)
    extracted = await asyncio.to_thread(llm.extract_json, prompt)

    if not extracted or "path" not in extracted or "value" not in extracted:
        return _text_response("수정 대상을 이해하지 못했습니다. 예: 'replicas를 3으로 바꿔줘'", intent)

    mod = YamlModification(path=extracted["path"], value=extracted["value"])
    result = yaml_editor.apply_modification(source, mod)

    if not result.success:
        return _text_response(f"YAML 수정 실패: {result.error}", intent)

    session_manager.store_modified_values(req.session_id, result.data["modified_yaml"])

    diff = yaml_editor.generate_diff(source, result.data["modified_yaml"])

    return ChatResponse(
        contents=[
            ContentBlock(
                type=ContentType.TEXT,
                body=f"`{mod.path}`: `{result.data['old_value']}` → `{mod.value}` 로 변경했습니다.",
            ),
            ContentBlock(type=ContentType.DIFF, body=diff),
        ],
        intent=intent,
    )


async def _handle_diff_show(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)

    if not session.original_values or not session.modified_values:
        return _text_response("비교할 변경사항이 없습니다. 먼저 values를 수정해주세요.", intent)

    diff = yaml_editor.generate_diff(session.original_values, session.modified_values)
    if not diff:
        return _text_response("변경된 내용이 없습니다.", intent)

    return ChatResponse(
        contents=[ContentBlock(type=ContentType.DIFF, body=diff)],
        intent=intent,
    )


async def _handle_file_save(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)

    yaml_text = session.modified_values or session.original_values
    if not yaml_text:
        return _text_response("저장할 values가 없습니다.", intent)

    release = session.current_release or "unknown"
    result = yaml_editor.save_values(release, yaml_text, original_text=session.original_values)

    if not result.success:
        return _text_response(f"저장 실패: {result.error}", intent)

    session_manager.mark_saved(req.session_id, result.data["path"])

    contents = [
        ContentBlock(type=ContentType.TEXT, body=f"저장 완료: `{result.data['filename']}`"),
        ContentBlock(type=ContentType.CODE, body=result.data["path"], language="path"),
    ]
    if result.data.get("backup_path"):
        contents.append(ContentBlock(type=ContentType.TEXT, body=f"원본 백업: `{Path(result.data['backup_path']).name}`"))

    return ChatResponse(contents=contents, intent=intent)


async def _handle_command_generate(req: ChatRequest, intent: IntentType) -> ChatResponse:
    session = session_manager.get(req.session_id)

    if not session.current_release:
        return _text_response("릴리스가 선택되지 않았습니다.", intent)

    values_path = session.last_saved_path
    if not values_path:
        return _text_response("먼저 values 파일을 저장해주세요.", intent)

    cmd = helm.generate_upgrade_command(
        session.current_release, session.current_namespace, values_path
    )

    return ChatResponse(
        contents=[
            ContentBlock(type=ContentType.TEXT, body="아래 명령어로 적용할 수 있습니다. `<CHART>`를 실제 차트 경로로 바꿔주세요."),
            ContentBlock(type=ContentType.COMMAND, body=cmd, language="bash"),
        ],
        intent=intent,
    )


async def _handle_unknown(req: ChatRequest, intent: IntentType) -> ChatResponse:
    return _text_response(
        "다음 작업을 수행할 수 있습니다:\n"
        "• Pod 상태 분석: 'backend-api pod 상태 확인해줘'\n"
        "• Helm values 조회: 'frontend values 보여줘'\n"
        "• YAML 수정: 'replicas를 3으로 바꿔줘'\n"
        "• diff 확인: 'diff 보여줘'\n"
        "• 저장: '저장해줘'\n"
        "• 적용 명령 생성: 'upgrade 명령 생성해줘'",
        intent,
    )


# --- Helpers ---


def _text_response(text: str, intent: IntentType) -> ChatResponse:
    return ChatResponse(contents=[ContentBlock(type=ContentType.TEXT, body=text)], intent=intent)


def _extract_pod_ref(message: str, current_pod: str | None, current_ns: str) -> tuple[str | None, str]:
    namespace = current_ns

    ns_match = re.search(r"(?:-n|--namespace|네임스페이스)\s+([a-z0-9][a-z0-9\-]*[a-z0-9])", message)
    if ns_match:
        namespace = ns_match.group(1)

    slash_match = re.search(r"([a-z0-9][a-z0-9\-]*)/([a-z0-9][a-z0-9\-]*[a-z0-9])", message)
    if slash_match:
        return slash_match.group(2), slash_match.group(1)

    words = message.split()
    for word in words:
        if re.match(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$", word) and len(word) > 2 and word not in _STOP_WORDS:
            return word, namespace
    return current_pod, namespace


def _extract_release_ref(message: str, current_release: str | None, current_ns: str) -> tuple[str | None, str]:
    words = message.split()
    for word in words:
        if re.match(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$", word) and len(word) > 2 and word not in _STOP_WORDS:
            return word, current_ns
    return current_release, current_ns


def _flatten_keys(data: dict, prefix: str = "") -> list[str]:
    keys = []
    for k, v in data.items():
        full = f"{prefix}.{k}" if prefix else str(k)
        keys.append(full)
        if isinstance(v, dict):
            keys.extend(_flatten_keys(v, full))
    return keys


_STOP_WORDS = {
    "pod", "pods", "helm", "values", "get", "show", "describe",
    "상태", "분석", "확인", "조회", "보여줘", "보여", "해줘",
    "로그", "이벤트", "문제", "에러", "오류", "diff",
    "저장", "수정", "변경", "바꿔", "설정", "명령",
    "upgrade", "generate", "save", "modify",
}

_HANDLERS = {
    IntentType.POD_ANALYZE: _handle_pod_analyze,
    IntentType.HELM_VALUES_GET: _handle_helm_values_get,
    IntentType.YAML_MODIFY: _handle_yaml_modify,
    IntentType.DIFF_SHOW: _handle_diff_show,
    IntentType.FILE_SAVE: _handle_file_save,
    IntentType.COMMAND_GENERATE: _handle_command_generate,
    IntentType.UNKNOWN: _handle_unknown,
}
