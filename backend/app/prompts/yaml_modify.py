def build_field_extraction_prompt(user_message: str, available_keys: list[str]) -> str:
    keys_str = "\n".join(f"- {k}" for k in available_keys)

    return f"""사용자가 YAML 값 변경을 요청했습니다.

[사용자 요청]
{user_message}

[사용 가능한 키 목록]
{keys_str}

위 키 목록에서 사용자가 변경하려는 키와 새 값을 JSON으로 추출하세요.
반드시 아래 형식으로만 응답하세요:
{{"path": "키.경로", "value": 새값}}

키 목록에 없는 키를 만들어내지 마세요.
값의 타입(숫자, 문자열, boolean)을 유지하세요."""
