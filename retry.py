"""
LLM 重试包装器
封装带指数退避的重试逻辑，处理 429/5xx/超时等瞬态错误
"""
import logging
import time
from typing import Any
from config import settings

logger = logging.getLogger("zhice-platform.retry")


def get_llm_with_retry(llm):
    """
    为 LLM 实例配置重试策略。
    ChatOpenAI 内部使用 tenacity 做重试，这里通过 max_retries 参数控制。

    重试行为：
    - 429 速率限制 → 指数退避（由 OpenAI SDK 的 max_retries 控制）
    - 5xx 服务端错误 → 同上
    - 超时 → 同上
    - 401/403 认证错误 → 不重试（SDK 自动识别）

    Args:
        llm: ChatOpenAI 实例
    Returns:
        配置好重试的 LLM 实例（原地修改并返回）
    """
    # ChatOpenAI 的 max_retries 控制 SDK 层面的重试（含 429/5xx/超时）
    llm.max_retries = settings.LLM_MAX_RETRIES

    logger.info(f"[Retry] LLM 重试配置: max_retries={settings.LLM_MAX_RETRIES}")
    return llm


class RetryStats:
    """追踪重试统计（用于日志和监控）"""

    def __init__(self):
        self.total_calls = 0
        self.total_retries = 0
        self.total_errors = 0
        self._last_error = None

    def record_call(self):
        self.total_calls += 1

    def record_retry(self, attempt: int, error: Exception):
        self.total_retries += 1
        self._last_error = str(error)
        logger.warning(f"[Retry] 第 {attempt} 次重试: {error}")

    def record_error(self, error: Exception):
        self.total_errors += 1
        logger.error(f"[Retry] 重试耗尽，最终失败: {error}")

    def get_stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_retries": self.total_retries,
            "total_errors": self.total_errors,
            "last_error": self._last_error,
        }


# 全局统计实例
retry_stats = RetryStats()
