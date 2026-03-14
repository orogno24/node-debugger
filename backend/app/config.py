import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

MODEL_PATH = os.getenv(
    "MODEL_PATH",
    str(BASE_DIR / "models" / "qwen3-1.7b-instruct-q4_k_m.gguf"),
)

OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(BASE_DIR / "outputs")))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# llama.cpp 추론 파라미터
LLM_CONTEXT_SIZE = int(os.getenv("LLM_CONTEXT_SIZE", "2048"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_THREADS = int(os.getenv("LLM_THREADS", str(os.cpu_count() or 4)))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))

# Helm / kubectl
HELM_BINARY = os.getenv("HELM_BINARY", "helm")
KUBECTL_BINARY = os.getenv("KUBECTL_BINARY", "kubectl")
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))

ALLOWED_NAMESPACES: list[str] | None = (
    os.getenv("ALLOWED_NAMESPACES", "").split(",")
    if os.getenv("ALLOWED_NAMESPACES")
    else None
)

# 수정 가능한 YAML 경로 화이트리스트
# 패턴: 정확한 경로 또는 와일드카드 접두사("resources.*" 등)
# None이면 제한 없음 (개발 모드)
_raw_paths = os.getenv("ALLOWED_MODIFY_PATHS", "")
ALLOWED_MODIFY_PATHS: list[str] | None = (
    [p.strip() for p in _raw_paths.split(",") if p.strip()]
    if _raw_paths
    else None
)

# 기본 화이트리스트 예시 (환경변수 미설정 시 사용할 기본값)
DEFAULT_MODIFY_PATHS = [
    "replicaCount",
    "image.tag",
    "image.repository",
    "resources.*",
    "env.*",
    "service.port",
    "service.type",
    "ingress.enabled",
    "autoscaling.*",
    "nodeSelector.*",
    "tolerations.*",
    "affinity.*",
]
