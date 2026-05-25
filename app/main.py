"""
FastAPI 应用入口
服装电商智能客服 Web 服务
"""
import os
import sys
import logging
from pathlib import Path

# 禁用 tqdm 进度条（解决 FastAPI 环境下的 stderr 错误）
os.environ["TQDM_DISABLE"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings
from app.routes import router


# ========== 日志配置 ==========
def setup_logging():
    """配置日志"""
    os.makedirs(os.path.dirname(settings.LOG_FILE) if settings.LOG_FILE else "./logs", exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.LOG_FILE, encoding="utf-8"),
        ],
    )


# ========== 生命周期事件 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    logger = logging.getLogger("zhice-platform")
    logger.info("=" * 50)
    logger.info(f"🚀 {settings.APP_TITLE} v{settings.APP_VERSION} 启动中...")
    logger.info(f"📡 服务地址: http://{settings.APP_HOST}:{settings.APP_PORT}")
    logger.info(f"🤖 LLM 模型: {settings.LLM_MODEL}")
    logger.info(f"📊 向量数据库: {settings.CHROMA_PERSIST_DIR}")
    logger.info("=" * 50)

    # 检查向量数据库是否存在
    chroma_path = Path(settings.CHROMA_PERSIST_DIR)
    if not chroma_path.exists() or not any(chroma_path.iterdir()):
        logger.warning("⚠️  向量数据库为空，请先运行 'python ingest.py --sample' 导入示例数据")

    yield

    logger.info("👋 服务关闭中...")


# ========== 创建 FastAPI 应用 ==========
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="基于 LangChain + RAG 的服装电商智能客服系统",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册中间件（后添加的先执行，LoggingMiddleware 放最后使其成为最外层）
from middleware.auth import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

# 静态前端
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# 注册路由
app.include_router(router)


# ========== 启动入口 ==========
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )
