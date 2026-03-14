from __future__ import annotations

import json
from typing import Any

from app.models.schemas import IssueClassification, IssueType, PodData

_ISSUE_HINTS: dict[IssueType, str] = {
    IssueType.OOM_KILLED: (
        "이 Pod의 컨테이너가 메모리 초과(OOMKilled)로 종료되었습니다.\n"
        "evidence의 memory_limit, restart_count, exit_code를 근거로 설명하세요.\n"
        "로그가 있다면 메모리 관련 단서를 지적하세요."
    ),
    IssueType.CRASH_LOOP: (
        "이 Pod의 컨테이너가 반복적으로 크래시(CrashLoopBackOff)하고 있습니다.\n"
        "evidence의 last_exit_code, restart_count를 근거로 설명하세요.\n"
        "이전 컨테이너 로그에서 에러 원인을 찾아 지적하세요."
    ),
    IssueType.IMAGE_PULL: (
        "이 Pod의 컨테이너 이미지를 가져올 수 없습니다(ImagePullBackOff).\n"
        "evidence의 message에서 이미지 이름과 레지스트리 정보를 근거로 설명하세요."
    ),
    IssueType.FAILED_SCHEDULING: (
        "이 Pod이 어떤 노드에도 스케줄링되지 못하고 있습니다(FailedScheduling).\n"
        "evidence의 event_message에서 부족한 리소스나 nodeSelector 문제를 근거로 설명하세요."
    ),
    IssueType.PROBE_FAILURE: (
        "이 Pod의 헬스체크 Probe가 실패하고 있습니다.\n"
        "evidence의 probe_type, event_count를 근거로 어떤 probe가 몇 번 실패했는지 설명하세요."
    ),
    IssueType.UNKNOWN: (
        "규칙 기반 분류에서 명확한 문제 유형을 특정하지 못했습니다.\n"
        "아래 Pod 상태와 이벤트 데이터를 보고 현재 상태를 사실 중심으로 요약하세요."
    ),
}


def build_pod_analysis_prompt(
    pod: PodData,
    classification: IssueClassification,
) -> str:
    hint = _ISSUE_HINTS.get(classification.issue_type, _ISSUE_HINTS[IssueType.UNKNOWN])
    evidence_json = json.dumps(classification.evidence, indent=2, ensure_ascii=False)

    sections = [
        f"[규칙 분류 결과]\n"
        f"issue_type: {classification.issue_type.value}\n"
        f"confidence: {classification.confidence.value}\n"
        f"affected_container: {classification.affected_container or 'N/A'}",
        f"[근거 데이터]\n{evidence_json}",
    ]

    if classification.relevant_logs:
        sections.append(f"[관련 로그 (마지막 {len(classification.relevant_logs.splitlines())}줄)]\n{classification.relevant_logs}")

    if classification.issue_type == IssueType.UNKNOWN:
        pod_summary = {
            "phase": pod.phase,
            "conditions": pod.conditions,
            "containers": [
                {"name": c.name, "ready": c.ready, "restart_count": c.restart_count,
                 "state": c.state, "last_state": c.last_state}
                for c in pod.containers
            ],
        }
        sections.append(f"[Pod 상태 전체]\n{json.dumps(pod_summary, indent=2, ensure_ascii=False)}")
        if pod.events:
            sections.append(f"[이벤트]\n{json.dumps(pod.events[:10], indent=2, ensure_ascii=False)}")

    data_block = "\n\n".join(sections)

    return f"""{hint}

{data_block}

아래 규칙을 따르세요:
1. 현재 상태를 한 문장으로 요약하세요.
2. 근거 데이터에서 확인되는 사실만 나열하세요.
3. 추측하지 마세요. evidence에 없는 내용을 만들지 마세요.
4. 한국어로 답하세요."""
