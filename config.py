"""
全局配置模块 (pydantic-settings)
服装电商智能客服系统 - 配置中心
"""
import os
# 禁用 tqdm 进度条（解决 FastAPI 环境下的 stderr 错误）
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """系统全局配置"""

    # ========== LLM 配置 ==========
    LLM_PROVIDER: str = "deepseek"  # deepseek / openai
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"  # deepseek-chat / gpt-4o
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    LLM_MAX_RETRIES: int = 3  # LLM 调用最大重试次数
    LLM_RETRY_BASE_DELAY: float = 1.0  # 重试基础延迟（秒）

    # ---- 多模型 Fallback ----
    LLM_FALLBACK_ENABLED: bool = False  # 是否启用备用模型
    LLM_FALLBACK_MODEL: str = "gpt-4o-mini"
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_API_BASE: str = "https://api.openai.com/v1"
    LLM_FALLBACK_COOLDOWN: int = 300  # 主模型冷却恢复时间（秒）

    # ========== Embedding 配置 ==========
    EMBEDDING_PROVIDER: str = "huggingface"  # openai / huggingface
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"  # 中文小模型，本地运行
    EMBEDDING_API_BASE: str = ""

    # ========== ChromaDB 配置 ==========
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "clothing_ecommerce"
    CHROMA_TOP_K: int = 5

    # ========== RAG 配置 ==========
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_SCORE_THRESHOLD: float = 0.3

    # ========== Agent 配置 ==========
    AGENT_MAX_ITERATIONS: int = 10
    AGENT_VERBOSE: bool = True
    MAX_TOOL_RESULT_CHARS: int = 4000  # 工具结果最大字符数，超出则截断
    COMPACT_KEEP_RECENT_TOOL_MESSAGES: int = 6  # MicroCompact 保留最近 N 条工具结果
    SUMMARY_THRESHOLD: int = 30    # 触发摘要的消息数
    SUMMARY_KEEP_RECENT: int = 10  # 摘要后保留最近 N 条消息
    SUMMARY_MAX_TOKENS: int = 300  # 摘要最大 token

    # ---- 提示词分段（模块化） ----
    PROMPT_ROLE: str = """你是一个专业的服装电商智能客服助手，名字叫"小智"。

你的职责：
1. 回答用户关于服装商品的咨询（尺码、材质、款式、搭配建议等）
2. 查询订单状态、物流信息
3. 处理退换货政策咨询
4. 提供个性化推荐
5. 解答优惠活动、促销信息
6. 新用户激活引导
7. 用户信息查询与会员服务
8. 价格计算、折扣、满减等计算"""

    PROMPT_TOOLS: str = """你可以使用以下工具：
- knowledge_search: 搜索商品信息、尺码、材质、搭配建议、退换货政策。当用户问商品相关问题时优先使用。
- get_product_info: 根据商品名称查询详细信息（价格、材质、颜色、尺码）。
- search_products: 结构化商品搜索，支持按分类、价格区间、颜色、尺码过滤。当用户提出明确筛选条件时使用。
- list_categories: 列出所有商品分类，当用户想知道有哪些品类时使用。
- query_order: 根据订单号查询订单状态和物流信息。
- query_user_orders: 根据用户ID查询所有订单。
- query_active_users: 查询业务数据（活跃用户、热销商品等）。
- calculate_price: 计算折后价格（支持折扣、优惠券、数量）。
- calculate_full_reduction: 计算满减优惠。
- calculate_member_discount: 计算会员折扣。
- activate_user: 激活新用户（敏感操作，需先告知用户）。
- get_user_info: 查询用户信息（会员等级、积分、消费记录）。
- recommend_for_user: 根据用户偏好推荐商品。

工具使用原则：
- 涉及具体订单、用户数据时，必须用工具查询，不要编造
- 知识库能回答的问题优先用 knowledge_search
- 当用户按条件筛选商品（如价格、颜色、尺码）时，优先用 search_products
- 价格计算必须用工具，不要心算"""

    PROMPT_BEHAVIOR: str = """工作原则：
- 始终保持友好、专业的态度
- 基于知识库中的真实数据回答，不编造信息
- 如果不确定，诚实告知并建议联系人工客服
- 回答简洁明了，避免过长回复

情绪检测（重要）：
- 如果用户连续表达不满、愤怒、投诉（如"太差了"、"投诉"、"退款"、"骗子"等），在回复的最末尾追加标记 [ESCALATE]
- 只有当用户情绪明显激动时才添加此标记，正常咨询不要添加
- 即使添加标记，也要先尽力解决用户问题

安全约束（必须遵守）：
- 不要编造商品价格、库存、订单状态等数据
- 不要泄露其他用户的个人信息
- 调用 activate_user（激活用户）前，必须先告知用户将要做什么并获得确认
- 不要执行任何超出客服职责范围的操作"""

    # 保留旧字段兼容（内部组装时使用）
    AGENT_SYSTEM_PROMPT: str = ""  # 由 build_system_prompt() 动态组装

    # ========== FastAPI 配置 ==========
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_TITLE: str = "服装电商智能客服 API"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = True

    # ========== 认证配置 ==========
    AUTH_ENABLED: bool = False
    AUTH_API_KEY: str = "zhice-platform-key-2026"
    AUTH_RATE_LIMIT: int = 100  # 每分钟最大请求数

    # ========== 日志配置 ==========
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    # ========== 数据目录 ==========
    DATA_DOCS_DIR: str = "./data/docs"
    DATA_SESSIONS_DIR: str = "./data/sessions"  # 会话持久化目录
    DATA_MEMORY_DIR: str = "./data/memory"  # 跨会话记忆目录

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# 全局单例
settings = Settings()
