from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ContentType(str, Enum):
    TEXT = "text"
    CODE = "code"
    YAML = "yaml"
    DIFF = "diff"
    COMMAND = "command"


class WorkStage(str, Enum):
    IDLE = "idle"
    VALUES_LOADED = "values_loaded"
    VALUES_MODIFIED = "values_modified"
    DIFF_REVIEWED = "diff_reviewed"
    FILE_SAVED = "file_saved"


class IntentType(str, Enum):
    POD_ANALYZE = "pod_analyze"
    HELM_VALUES_GET = "helm_values_get"
    YAML_MODIFY = "yaml_modify"
    DIFF_SHOW = "diff_show"
    FILE_SAVE = "file_save"
    COMMAND_GENERATE = "command_generate"
    UNKNOWN = "unknown"


# --- 요청/응답 ---


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ContentBlock(BaseModel):
    type: ContentType = ContentType.TEXT
    body: str
    language: str | None = None


class ChatResponse(BaseModel):
    role: MessageRole = MessageRole.ASSISTANT
    contents: list[ContentBlock]
    intent: IntentType | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


# --- 세션 ---


class SessionState(BaseModel):
    session_id: str = "default"
    current_namespace: str = "default"
    current_pod: str | None = None
    current_release: str | None = None
    original_values: str | None = None
    modified_values: str | None = None
    work_stage: WorkStage = WorkStage.IDLE
    last_saved_path: str | None = None


# --- 도구 결과 ---


class ToolResult(BaseModel):
    tool: str
    success: bool
    data: Any = None
    error: str | None = None


# --- YAML 수정 지시 ---


class YamlModification(BaseModel):
    path: str
    value: Any


# --- Pod 분석 ---


class IssueType(str, Enum):
    OOM_KILLED = "oom_killed"
    CRASH_LOOP = "crash_loop"
    IMAGE_PULL = "image_pull"
    FAILED_SCHEDULING = "failed_scheduling"
    PROBE_FAILURE = "probe_failure"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContainerInfo(BaseModel):
    name: str
    ready: bool
    restart_count: int
    state: dict[str, Any]
    last_state: dict[str, Any]
    resources: dict[str, Any]


class PodData(BaseModel):
    name: str
    namespace: str
    phase: str | None = None
    conditions: list[dict[str, Any]] = []
    containers: list[ContainerInfo] = []
    events: list[dict[str, Any]] = []
    logs: str | None = None
    previous_logs: str | None = None


class IssueClassification(BaseModel):
    issue_type: IssueType
    confidence: Confidence
    affected_container: str | None = None
    evidence: dict[str, Any] = {}
    relevant_logs: str | None = None
