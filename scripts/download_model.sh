#!/bin/bash
# Qwen3-1.7B-Instruct GGUF Q4_K_M 다운로드 스크립트
# 인터넷이 되는 환경에서 실행한 후, 모델 파일을 폐쇄망으로 옮긴다.

set -e

MODEL_DIR="$(cd "$(dirname "$0")/.." && pwd)/models"
MODEL_FILE="qwen3-1.7b-instruct-q4_k_m.gguf"
MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"

# HuggingFace 모델 URL (커뮤니티 양자화)
HF_REPO="Qwen/Qwen3-1.7B-GGUF"
HF_FILE="Qwen3-1.7B-Q4_K_M.gguf"
DOWNLOAD_URL="https://huggingface.co/${HF_REPO}/resolve/main/${HF_FILE}"

mkdir -p "${MODEL_DIR}"

if [ -f "${MODEL_PATH}" ]; then
    echo "[INFO] 모델 파일이 이미 존재합니다: ${MODEL_PATH}"
    echo "[INFO] 크기: $(du -h "${MODEL_PATH}" | cut -f1)"
else
    echo "[INFO] 모델 다운로드 시작..."
    echo "[INFO] URL: ${DOWNLOAD_URL}"
    echo "[INFO] 저장 경로: ${MODEL_PATH}"
    echo ""

    if command -v wget &> /dev/null; then
        wget -O "${MODEL_PATH}" "${DOWNLOAD_URL}"
    elif command -v curl &> /dev/null; then
        curl -L -o "${MODEL_PATH}" "${DOWNLOAD_URL}"
    else
        echo "[ERROR] wget 또는 curl이 필요합니다."
        exit 1
    fi

    echo ""
    echo "[INFO] 다운로드 완료: $(du -h "${MODEL_PATH}" | cut -f1)"
fi

echo ""
echo "=== 모델 검증 ==="
echo "파일: ${MODEL_PATH}"
echo "크기: $(du -h "${MODEL_PATH}" | cut -f1)"

if [ "$(stat -f%z "${MODEL_PATH}" 2>/dev/null || stat -c%s "${MODEL_PATH}" 2>/dev/null)" -gt 500000000 ]; then
    echo "상태: OK (500MB 이상)"
else
    echo "상태: WARNING - 파일이 너무 작습니다. 다운로드가 불완전할 수 있습니다."
fi

echo ""
echo "=== 다음 단계 ==="
echo "1. 이 파일을 폐쇄망 클러스터 노드로 복사하세요:"
echo "   scp ${MODEL_PATH} <node>:/data/models/${MODEL_FILE}"
echo ""
echo "2. 또는 PV에 마운트할 경로에 배치하세요."
