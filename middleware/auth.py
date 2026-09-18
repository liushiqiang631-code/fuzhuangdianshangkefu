"""
认证与日志中间件
"""
import time
import secrets
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config import settings

logger = logging.getLogger("zhice-platform.auth")


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件"""

    # 不需要认证的路径（页面与公开资源）
    # 注意：/admin 下的管理 API 不在白名单内，开启认证后需携带 X-API-Key
    WHITELIST = {
        "/", "/ui", "/admin", "/knowledge",
        "/health", "/health/llm",
        "/docs", "/openapi.json", "/redoc",
    }
    WHITELIST_PREFIXES = ("/static/", "/uploads/")

    async def dispatch(self, request: Request, call_next):
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in self.WHITELIST or path.startswith(self.WHITELIST_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not api_key or not secrets.compare_digest(api_key, settings.AUTH_API_KEY):
            return JSONResponse({"detail": "无效的 API Key"}, status_code=401)

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

    MAX_TRACKED_IPS = 10000

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
            if len(self.request_counts) >= self.MAX_TRACKED_IPS:
                # 防止内存无限增长：丢弃全量过期后再超限时重置
                self.request_counts.clear()
            self.request_counts[client_ip] = []

        # 检查速率
        if len(self.request_counts[client_ip]) >= self.max_requests:
            return JSONResponse(
                {"detail": f"请求过于频繁，限制每分钟 {self.max_requests} 次"},
                status_code=429,
            )

        self.request_counts[client_ip].append(now)
        return await call_next(request)
