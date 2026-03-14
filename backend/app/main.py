import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("K8s ChatOps Console 시작")
    try:
        from app import llm
        await asyncio.to_thread(llm.load_model)
    except Exception as e:
        logger.warning("LLM 로드 실패 (모델 파일 없이 실행 중): %s", e)
    yield
    logger.info("K8s ChatOps Console 종료")


app = FastAPI(title="K8s ChatOps Console", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    from app import llm
    return {"status": "ok", "llm_loaded": llm.is_loaded()}


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    logger.info("정적 파일 서빙: %s", STATIC_DIR)
