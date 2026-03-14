from __future__ import annotations

import logging

from app.models.schemas import (
    Confidence,
    ContainerInfo,
    IssueClassification,
    IssueType,
    PodData,
)
from app.tools import kube

logger = logging.getLogger(__name__)

LOG_TAIL_LIMIT = 30


def collect_pod_data(pod_name: str, namespace: str) -> PodData | str:
    """Pod 관련 데이터를 모두 수집한다. 실패 시 에러 메시지 문자열을 반환한다."""
    status_result = kube.get_pod_status(pod_name, namespace)
    if not status_result.success:
        return f"Pod 조회 실패: {status_result.error}"

    events_result = kube.get_pod_events(pod_name, namespace)
    logs_result = kube.get_pod_logs(pod_name, namespace)
    prev_logs_result = kube.get_pod_previous_logs(pod_name, namespace)

    pod_data = PodData(**status_result.data)
    pod_data.events = events_result.data if events_result.success else []
    pod_data.logs = logs_result.data if logs_result.success else None
    pod_data.previous_logs = prev_logs_result.data if prev_logs_result.success else None

    return pod_data


def classify_issue(pod: PodData) -> IssueClassification:
    """규칙 기반으로 문제 유형을 판별한다. 순서가 중요하다."""
    checkers = [
        _check_oom_killed,
        _check_crash_loop,
        _check_image_pull,
        _check_scheduling,
        _check_probe_failure,
    ]
    for checker in checkers:
        result = checker(pod)
        if result is not None:
            return result

    return IssueClassification(
        issue_type=IssueType.UNKNOWN,
        confidence=Confidence.LOW,
        evidence={"phase": pod.phase, "container_count": len(pod.containers)},
    )


def analyze_pod(pod_name: str, namespace: str) -> tuple[PodData | None, IssueClassification | None, str | None]:
    """Pod 분석 전체 파이프라인. (pod_data, classification, error) 를 반환한다."""
    result = collect_pod_data(pod_name, namespace)
    if isinstance(result, str):
        return None, None, result

    classification = classify_issue(result)

    relevant = _pick_relevant_logs(result, classification)
    if relevant:
        classification.relevant_logs = relevant

    return result, classification, None


# ── 규칙 함수들 ──


def _check_oom_killed(pod: PodData) -> IssueClassification | None:
    for c in pod.containers:
        reason, exit_code = _terminated_info(c)

        if reason == "OOMKilled":
            return _build(
                IssueType.OOM_KILLED, Confidence.HIGH, c,
                exit_code=exit_code, memory_limit=c.resources.get("limits", {}).get("memory"),
            )

        if exit_code == 137:
            return _build(
                IssueType.OOM_KILLED, Confidence.MEDIUM, c,
                exit_code=137, memory_limit=c.resources.get("limits", {}).get("memory"),
                note="exit_code 137(SIGKILL). OOMKilled 가능성 높음.",
            )
    return None


def _check_crash_loop(pod: PodData) -> IssueClassification | None:
    for c in pod.containers:
        state_reason = c.state.get("reason", "")
        if state_reason == "CrashLoopBackOff":
            last_reason, last_exit = _terminated_info(c)
            return _build(
                IssueType.CRASH_LOOP, Confidence.HIGH, c,
                last_exit_code=last_exit, last_reason=last_reason,
            )

        if c.restart_count >= 5 and c.last_state.get("status") == "terminated":
            last_reason, last_exit = _terminated_info(c)
            return _build(
                IssueType.CRASH_LOOP, Confidence.MEDIUM, c,
                last_exit_code=last_exit, last_reason=last_reason,
                note=f"restart_count={c.restart_count}, 반복 종료 감지.",
            )
    return None


def _check_image_pull(pod: PodData) -> IssueClassification | None:
    for c in pod.containers:
        reason = c.state.get("reason", "")
        if reason in ("ImagePullBackOff", "ErrImagePull"):
            return _build(
                IssueType.IMAGE_PULL, Confidence.HIGH, c,
                message=c.state.get("message"),
            )

    for ev in pod.events:
        if ev.get("reason") == "Failed" and _contains_any(ev.get("message", ""), ["pull", "image"]):
            return IssueClassification(
                issue_type=IssueType.IMAGE_PULL,
                confidence=Confidence.MEDIUM,
                evidence={"event_message": ev.get("message")},
            )
    return None


def _check_scheduling(pod: PodData) -> IssueClassification | None:
    if pod.phase != "Pending":
        return None

    for ev in pod.events:
        if ev.get("reason") == "FailedScheduling":
            return IssueClassification(
                issue_type=IssueType.FAILED_SCHEDULING,
                confidence=Confidence.HIGH,
                evidence={
                    "event_message": ev.get("message"),
                    "source": ev.get("source"),
                },
            )
    return None


def _check_probe_failure(pod: PodData) -> IssueClassification | None:
    for ev in pod.events:
        reason = ev.get("reason", "")
        message = ev.get("message", "").lower()

        if reason == "Unhealthy" or "probe" in reason.lower():
            probe_type = "unknown"
            if "readiness" in message:
                probe_type = "readiness"
            elif "liveness" in message:
                probe_type = "liveness"
            elif "startup" in message:
                probe_type = "startup"

            affected = _find_unready_container(pod)
            return IssueClassification(
                issue_type=IssueType.PROBE_FAILURE,
                confidence=Confidence.HIGH if reason == "Unhealthy" else Confidence.MEDIUM,
                affected_container=affected,
                evidence={
                    "probe_type": probe_type,
                    "event_message": ev.get("message"),
                    "event_count": ev.get("count"),
                },
            )
    return None


# ── 헬퍼 ──


def _terminated_info(c: ContainerInfo) -> tuple[str | None, int | None]:
    """현재 또는 이전 state에서 terminated 정보를 추출한다."""
    for state in [c.last_state, c.state]:
        if state.get("status") == "terminated":
            return state.get("reason"), state.get("exit_code")
    return None, None


def _build(
    issue: IssueType, confidence: Confidence, c: ContainerInfo, **evidence
) -> IssueClassification:
    evidence["restart_count"] = c.restart_count
    return IssueClassification(
        issue_type=issue,
        confidence=confidence,
        affected_container=c.name,
        evidence={k: v for k, v in evidence.items() if v is not None},
    )


def _find_unready_container(pod: PodData) -> str | None:
    for c in pod.containers:
        if not c.ready:
            return c.name
    return pod.containers[0].name if pod.containers else None


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _pick_relevant_logs(pod: PodData, classification: IssueClassification) -> str | None:
    """분류 유형에 맞는 로그를 선택하고 길이를 제한한다."""
    if classification.issue_type in (IssueType.OOM_KILLED, IssueType.CRASH_LOOP):
        logs = pod.previous_logs or pod.logs
    else:
        logs = pod.logs

    if not logs:
        return None

    lines = logs.strip().splitlines()
    return "\n".join(lines[-LOG_TAIL_LIMIT:])
