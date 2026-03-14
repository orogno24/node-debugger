const API_BASE = "/api";

export async function sendMessage(message, sessionId = "default") {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!res.ok) {
    throw new Error(`API 오류: ${res.status}`);
  }

  return res.json();
}

export async function getSession(sessionId = "default") {
  const res = await fetch(`${API_BASE}/session/${sessionId}`);
  if (!res.ok) {
    throw new Error(`세션 조회 실패: ${res.status}`);
  }
  return res.json();
}
