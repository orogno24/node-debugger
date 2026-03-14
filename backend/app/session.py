from app.models.schemas import SessionState, WorkStage


class SessionManager:
    """인메모리 세션 저장소. 단일 사용자 MVP 기준."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str = "default") -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def set_target_pod(self, session_id: str, pod: str, namespace: str) -> None:
        state = self.get(session_id)
        state.current_pod = pod
        state.current_namespace = namespace

    def set_target_release(self, session_id: str, release: str, namespace: str) -> None:
        state = self.get(session_id)
        state.current_release = release
        state.current_namespace = namespace

    def store_original_values(self, session_id: str, yaml_text: str) -> None:
        state = self.get(session_id)
        state.original_values = yaml_text
        state.modified_values = None
        state.work_stage = WorkStage.VALUES_LOADED

    def store_modified_values(self, session_id: str, yaml_text: str) -> None:
        state = self.get(session_id)
        state.modified_values = yaml_text
        state.work_stage = WorkStage.VALUES_MODIFIED

    def mark_diff_reviewed(self, session_id: str) -> None:
        state = self.get(session_id)
        state.work_stage = WorkStage.DIFF_REVIEWED

    def mark_saved(self, session_id: str, path: str) -> None:
        state = self.get(session_id)
        state.last_saved_path = path
        state.work_stage = WorkStage.FILE_SAVED

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


session_manager = SessionManager()
