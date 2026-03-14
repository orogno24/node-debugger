import re

from app.models.schemas import IntentType

_PATTERNS: list[tuple[IntentType, list[str]]] = [
    (IntentType.POD_ANALYZE, [
        r"pod.*(?:상태|분석|확인|로그|이벤트|에러|오류|문제|진단)",
        r"(?:상태|분석|확인|로그|이벤트|에러|오류|문제|진단).*pod",
        r"(?:왜|why).*(?:죽|restart|crash|fail|pending|error)",
        r"describe\s+pod",
    ]),
    (IntentType.HELM_VALUES_GET, [
        r"(?:values|밸류|설정값?).*(?:조회|보여|확인|가져)",
        r"(?:조회|보여|확인|가져).*(?:values|밸류|설정값?)",
        r"helm\s+(?:get\s+)?values",
        r"릴리스.*(?:설정|값)",
    ]),
    (IntentType.YAML_MODIFY, [
        r"(?:바꿔|변경|수정|설정).*(?:해줘|해 줘|하자|해라)",
        r"(?:replicas?|replica\s*count|image|resource|limit|cpu|memory|port).*(?:\d+|변경|수정|바꿔)",
        r"(?:\d+).*(?:으로|로)\s*(?:바꿔|변경|수정|설정)",
    ]),
    (IntentType.DIFF_SHOW, [
        r"diff",
        r"(?:차이|변경\s*사항|변경\s*점|비교).*(?:보여|확인|표시)",
        r"(?:보여|확인|표시).*(?:차이|변경\s*사항|변경\s*점|비교)",
        r"뭐가?\s*(?:바뀌|달라)",
    ]),
    (IntentType.FILE_SAVE, [
        r"저장",
        r"save",
        r"파일.*(?:만들|생성|내보)",
    ]),
    (IntentType.COMMAND_GENERATE, [
        r"(?:helm\s+)?upgrade.*(?:명령|커맨드|command)",
        r"(?:명령|커맨드|command).*(?:생성|만들|보여)",
        r"(?:어떻게|how).*(?:적용|apply|upgrade)",
        r"적용.*(?:명령|방법|커맨드)",
    ]),
]


def classify_intent(message: str) -> IntentType:
    text = message.lower().strip()
    for intent_type, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return intent_type
    return IntentType.UNKNOWN
