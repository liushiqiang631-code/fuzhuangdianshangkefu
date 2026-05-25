"""
认证与日志中间件
"""
import time
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

logger = logging.getLogger("zhice-platform.auth")


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件"""

    # 不需要认证的路径
    WHITELIST = ["/", "/health", "/health/llm", "/ui", "/admin", "/docs", "/openapi.json", "/redoc", "/feedback", "/escalate", "/upload"]

    async def dispatch(self, request: Request, call_next):
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        if request.url.path in self.WHITELIST or request.url.path.startswith("/static/") or request.url.path.startswith("/admin") or request.url.path.startswith("/uploads"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key != settings.AUTH_API_KEY:
            raise HTTPException(status_code=401, detail="无效的 API Key")

        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        elapsed = time.time() - start_time

        # 记录日志
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"time={elapsed:.3f}s "
            f"client={request.client.host if request.client else 'unknown'}"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的速率限制中间件（基于内存）"""

    def __init__(self, app, max_requests: int = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.AUTH_RATE_LIMIT
        self.request_counts = {}  # {client_ip: [timestamp, ...]}

    async def dispatch(self, request: Request, call_next):
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # 清理60秒前的记录
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                t for t in self.request_counts[client_ip] if now - t < 60
            ]
        else:
            self.request_counts[client_ip] = []

        # 检查速率
        if len(self.request_counts[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，限制每分钟 {self.max_requests} 次",
            )

        self.request_counts[client_ip].append(now)
        return await call_next(request)
