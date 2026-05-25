"""
LLM 工厂模块
支持主/备模型自动切换（Fallback）
"""
import time
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger("zhice-platform.llm_factory")


class FallbackLLM:
    """
    带 Fallback 的 LLM 包装器

    - 正常使用主模型
    - 主模型连续失败 N 次 → 自动切到备用模型
    - 冷却时间后自动尝试恢复主模型
    """

    def __init__(self):
        self._primary: Optional[ChatOpenAI] = None
        self._fallback: Optional[ChatOpenAI] = None
        self._consecutive_failures = 0
        self._failure_threshold = 3
        self._last_primary_failure = 0.0
        self._using_fallback = False

        self._init_primary()
        if settings.LLM_FALLBACK_ENABLED:
            self._init_fallback()

    def _init_primary(self):
        self._primary = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
        )
        logger.info(f"[LLM Factory] 主模型初始化: {settings.LLM_MODEL}")

    def _init_fallback(self):
        if not settings.LLM_FALLBACK_API_KEY:
            logger.warning("[LLM Factory] 备用模型未配置 API Key，跳过初始化")
            return
        self._fallback = ChatOpenAI(
            model=settings.LLM_FALLBACK_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            openai_api_key=settings.LLM_FALLBACK_API_KEY,
            openai_api_base=settings.LLM_FALLBACK_API_BASE,
        )
        logger.info(f"[LLM Factory] 备用模型初始化: {settings.LLM_FALLBACK_MODEL}")

    def _should_try_primary(self) -> bool:
        """是否应该尝试恢复主模型"""
        if not self._using_fallback:
            return True
        elapsed = time.time() - self._last_primary_failure
        return elapsed >= settings.LLM_FALLBACK_COOLDOWN

    def get_llm(self) -> ChatOpenAI:
        """获取当前应该使用的 LLM 实例"""
        if self._should_try_primary():
            self._using_fallback = False
            return self._primary
        if self._fallback:
            self._using_fallback = True
            return self._fallback
        return self._primary

    def record_success(self):
        """记录调用成功"""
        self._consecutive_failures = 0
        # 不立即切回主模型，等冷却时间到期后由 get_llm 自动恢复

    def record_failure(self, error: Exception):
        """记录调用失败"""
        self._consecutive_failures += 1
        logger.warning(
            f"[LLM Factory] 调用失败 ({self._consecutive_failures}/{self._failure_threshold}): {error}"
        )

        if self._consecutive_failures >= self._failure_threshold:
            self._last_primary_failure = time.time()
            if self._fallback and not self._using_fallback:
                self._using_fallback = True
                logger.warning(
                    f"[LLM Factory] 主模型连续失败 {self._failure_threshold} 次，切换到备用模型: {settings.LLM_FALLBACK_MODEL}"
                )

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def has_fallback(self) -> bool:
        """是否有备用模型可用"""
        return self._fallback is not None

    @property
    def model_name(self) -> str:
        if self._using_fallback and self._fallback:
            return settings.LLM_FALLBACK_MODEL
        return settings.LLM_MODEL


# 全局单例
_fallback_llm: Optional[FallbackLLM] = None


def get_fallback_llm() -> FallbackLLM:
    """获取 FallbackLLM 全局单例"""
    global _fallback_llm
    if _fallback_llm is None:
        _fallback_llm = FallbackLLM()
    return _fallback_llm
