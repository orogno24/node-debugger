# ============================================================
# Stage 1: 프론트엔드 빌드
# ============================================================
FROM node:20-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Python 의존성 빌드
# ============================================================
FROM python:3.11-slim AS python-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make cmake git pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

ENV FORCE_CMAKE=1
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF \
-DGGML_SSE42=OFF \
-DGGML_AVX=OFF \
-DGGML_AVX2=OFF \
-DGGML_AVX_VNNI=OFF \
-DGGML_BMI2=OFF \
-DGGML_FMA=OFF \
-DGGML_F16C=OFF \
-DGGML_AVX512=OFF \
-DGGML_AVX512_VBMI=OFF \
-DGGML_AVX512_VNNI=OFF \
-DGGML_AVX512_BF16=OFF \
-DGGML_AMX_TILE=OFF \
-DGGML_AMX_INT8=OFF \
-DGGML_AMX_BF16=OFF \
-DGGML_BLAS=OFF \
-DGGML_OPENMP=ON"

COPY backend/requirements.txt ./

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    pip install --no-cache-dir --prefix=/install --force-reinstall -v \
      --no-binary=llama-cpp-python llama-cpp-python

# ============================================================
# Stage 3: 런타임
# ============================================================
FROM python:3.11-slim AS runtime

ARG HELM_VERSION=3.16.3
ARG KUBECTL_VERSION=1.31.3

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libgomp1 \
    && curl -fsSL https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz \
       | tar xz -C /usr/local/bin --strip-components=1 linux-amd64/helm \
    && curl -fsSL -o /usr/local/bin/kubectl \
       https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-build /install /usr/local

WORKDIR /app
COPY backend/ ./
COPY --from=frontend-build /build/dist ./static/

RUN mkdir -p /app/models /app/outputs

ENV MODEL_PATH=/app/models/qwen3-1.7b-instruct-q4_k_m.gguf \
    OUTPUTS_DIR=/app/outputs \
    LLM_THREADS=4 \
    LLM_CONTEXT_SIZE=2048 \
    LLM_MAX_TOKENS=512 \
    LLM_TEMPERATURE=0.1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]