"""
Agent 模块
构建 Agent 并管理会话（增强推理能力）
使用 LangChain 1.2+ 的 create_agent API

P1 改进：提示词模块化 + 重试机制 + MicroCompact + token 追踪 + 记忆注入
"""
import uuid
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from config import settings
from retry import get_llm_with_retry, retry_stats
from llm_factory import get_fallback_llm
from memory import load_memories
from tools.knowledge import knowledge_search, get_product_info
from tools.analytics import query_order, query_user_orders, query_active_users
from tools.calculator import calculate_price, calculate_full_reduction, calculate_member_discount
from tools.user_activation import activate_user, get_user_info, recommend_for_user
from tools.product_search import search_products, list_categories

logger = logging.getLogger("zhice-platform.agent")

# ========== 会话持久化目录 ==========
SESSIONS_DIR = Path(settings.DATA_SESSIONS_DIR)


# ========== 系统提示词组装 ==========
def build_system_prompt(memory_context: str = "") -> str:
    """
    动态组装系统提示词（模块化）

    组装顺序：角色 → 工具指南 → 行为约束 → 动态上下文（时间、记忆）
    """
    parts = [
        settings.PROMPT_ROLE,
        "",
        settings.PROMPT_TOOLS,
        "",
        settings.PROMPT_BEHAVIOR,
    ]

    # 动态上下文
    dynamic = []
    dynamic.append(f"\n当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if memory_context:
        dynamic.append(f"\n{memory_context}")

    if dynamic:
        parts.append("\n---\n动态上下文：")
        parts.extend(dynamic)

    return "\n".join(parts)


# ========== 工具结果裁剪 ==========
def trim_tool_result(text: str, max_chars: int = None) -> str:
    """裁剪过大的工具结果，防止撑爆上下文"""
    limit = max_chars or settings.MAX_TOOL_RESULT_CHARS
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[结果已截断，原始长度 {len(text)} 字符]"


# ========== MicroCompact 上下文压缩 ==========
def compact_history(history: List, keep_recent: int = None) -> List:
    """
    MicroCompact：清理旧的工具结果，保留最近 N 条完整

    策略：
    - HumanMessage / AIMessage 保留不变
    - 最近 keep_recent 条 ToolMessage 保留完整
    - 更早的 ToolMessage 替换为占位符
    """
    if not history:
        return history

    n = keep_recent or settings.COMPACT_KEEP_RECENT_TOOL_MESSAGES

    # 找出所有 ToolMessage 的位置
    tool_indices = [i for i, msg in enumerate(history) if isinstance(msg, ToolMessage)]

    if len(tool_indices) <= n:
        return history  # 不需要压缩

    # 需要压缩的 ToolMessage 索引（保留最后 n 条）
    to_compact = tool_indices[:-n]

    # 创建压缩后的副本
    compacted = list(history)
    for idx in to_compact:
        original_len = len(compacted[idx].content) if compacted[idx].content else 0
        compacted[idx] = ToolMessage(
            content="[历史工具结果已清理]",
            tool_call_id=compacted[idx].tool_call_id,
        )
        logger.debug(f"[Compact] 清理 ToolMessage[{idx}], 原始长度 {original_len}")

    logger.info(f"[Compact] MicroCompact 完成: 清理了 {len(to_compact)} 条旧工具结果")
    return compacted


# ========== 对话摘要压缩 ==========
def _summarize_history(history: List) -> List:
    """
    当历史过长时，用 LLM 生成摘要替换旧消息

    策略：
    - 超过 SUMMARY_THRESHOLD 条消息时触发
    - 取前 N 条消息生成摘要
    - 保留最近 SUMMARY_KEEP_RECENT 条消息不动
    """
    threshold = settings.SUMMARY_THRESHOLD
    keep_recent = settings.SUMMARY_KEEP_RECENT

    if len(history) <= threshold:
        return history

    # 需要摘要的部分
    to_summarize = history[:-keep_recent]
    recent = history[-keep_recent:]

    # 构造摘要提示
    conversation_text = []
    for msg in to_summarize:
        if isinstance(msg, HumanMessage):
            conversation_text.append(f"用户: {str(msg.content)[:200]}")
        elif isinstance(msg, AIMessage):
            conversation_text.append(f"客服: {str(msg.content)[:200]}")

    if not conversation_text:
        return history

    summary_prompt = "请用中文将以下对话总结为一段简短摘要（不超过200字），保留关键信息如用户需求、已提供的商品推荐、订单信息等：\n\n" + "\n".join(conversation_text)

    try:
        fallback = get_fallback_llm()
        llm = fallback.get_llm()
        result = llm.invoke([HumanMessage(content=summary_prompt)])
        summary = result.content if hasattr(result, "content") else str(result)

        # 用摘要替换旧消息
        summary_msg = SystemMessage(content=f"[对话摘要] {summary}")
        logger.info(f"[Summary] 生成对话摘要: {len(summary)} 字，压缩了 {len(to_summarize)} 条消息")
        return [summary_msg] + recent

    except Exception as e:
        logger.warning(f"[Summary] 摘要生成失败，保留原始历史: {e}")
        return history


# ========== Agent 工具列表 ==========
AGENT_TOOLS = [
    knowledge_search,
    get_product_info,
    search_products,
    list_categories,
    query_order,
    query_user_orders,
    query_active_users,
    calculate_price,
    calculate_full_reduction,
    calculate_member_discount,
    activate_user,
    get_user_info,
    recommend_for_user,
]


# ========== LLM / Agent 全局单例 ==========
_agent = None
_agent_model_name = None


def _create_agent(llm) -> object:
    """用指定 LLM 创建 Agent"""
    llm = get_llm_with_retry(llm)
    return create_react_agent(model=llm, tools=AGENT_TOOLS)


def get_agent(force_rebuild: bool = False):
    """获取 Agent 全局单例（lazy 初始化，支持 fallback 切换）"""
    global _agent, _agent_model_name

    fallback = get_fallback_llm()
    current_model = fallback.model_name

    if _agent is None or force_rebuild or _agent_model_name != current_model:
        llm = fallback.get_llm()
        _agent = _create_agent(llm)
        _agent_model_name = current_model
        logger.info(f"[Agent] 初始化完成 model={current_model} fallback={fallback.is_using_fallback}")

    return _agent


# ========== LLM 健康检查 ==========
def check_llm_health() -> dict:
    """
    检查 LLM 连通性

    Returns:
        {"status": "healthy"/"unhealthy", "model": str, "latency_ms": int, "fallback_active": bool}
    """
    fallback = get_fallback_llm()
    llm = fallback.get_llm()
    start = time.time()

    try:
        # 发送极简请求验证连通性
        llm.invoke([HumanMessage(content="hi")])
        latency = int((time.time() - start) * 1000)
        return {
            "status": "healthy",
            "model": fallback.model_name,
            "latency_ms": latency,
            "fallback_active": fallback.is_using_fallback,
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        logger.warning(f"[Health] LLM 健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "model": fallback.model_name,
            "latency_ms": latency,
            "fallback_active": fallback.is_using_fallback,
            "error": str(e),
        }


# ========== SSE 事件构造 ==========
def _sse_event(event_type: str, data: dict) -> str:
    """构造 SSE 格式的事件字符串"""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ========== 消息序列化/反序列化 ==========
def _serialize_history(history: List) -> list:
    """将 chat_history 序列化为可存储的 dict 列表"""
    result = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "ai", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            result.append({"role": "tool", "content": msg.content, "tool_call_id": getattr(msg, "tool_call_id", "")})
    return result


def _deserialize_history(data: list) -> List:
    """从 dict 列表还原 chat_history"""
    result = []
    for item in data:
        role = item.get("role", "")
        content = item.get("content", "")
        if role == "human":
            result.append(HumanMessage(content=content))
        elif role == "ai":
            result.append(AIMessage(content=content))
        elif role == "tool":
            result.append(ToolMessage(content=content, tool_call_id=item.get("tool_call_id", "")))
    return result


# ========== Token 用量追踪 ==========
class TokenUsage:
    """单次请求的 token 用量"""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


# ========== 聊天会话 ==========
class ChatSession:
    """聊天会话管理"""

    def __init__(self, session_id: str = None, created_at: float = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.chat_history: List = []
        self.created_at = created_at or time.time()

    @classmethod
    def _from_file(cls, path: Path) -> Optional["ChatSession"]:
        """从磁盘文件恢复会话"""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            session = cls(
                session_id=data["session_id"],
                created_at=data.get("created_at", time.time()),
            )
            session.chat_history = _deserialize_history(data.get("chat_history", []))
            return session
        except Exception as e:
            logger.warning(f"[Session] 加载会话文件失败 {path}: {e}")
            return None

    def _save(self):
        """将会话持久化到磁盘"""
        try:
            SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "session_id": self.session_id,
                "chat_history": _serialize_history(self.chat_history),
                "created_at": self.created_at,
                "last_active": time.time(),
            }
            path = SESSIONS_DIR / f"{self.session_id}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[Session] 保存会话失败 {self.session_id}: {e}")

    def _build_messages(self, user_message: str) -> List:
        """构建发送给 LLM 的消息列表（含记忆注入 + MicroCompact + 摘要压缩）"""
        # 加载记忆
        memory_context = load_memories()

        # 组装系统提示词
        system_prompt = build_system_prompt(memory_context)

        # MicroCompact 压缩旧工具结果
        compacted_history = compact_history(self.chat_history)

        # 对话摘要压缩（当历史过长时）
        summarized_history = _summarize_history(compacted_history)

        # 组装消息
        messages = [SystemMessage(content=system_prompt)]
        for msg in summarized_history:
            messages.append(msg)
        messages.append(HumanMessage(content=user_message))

        return messages

    def chat(self, user_message: str) -> Dict:
        """
        处理用户消息并返回回复（阻塞模式）

        Returns:
            {"reply": str, "tools_used": list, "session_id": str, "token_usage": dict}
        """
        fallback = get_fallback_llm()

        for attempt in range(2):  # 最多尝试 2 次（主模型 + 备用模型）
            try:
                agent = get_agent(force_rebuild=(attempt > 0))
                messages = self._build_messages(user_message)

                retry_stats.record_call()

                # 调用 Agent
                result = agent.invoke({"messages": messages})

                # 记录成功
                fallback.record_success()

                # 提取回复和工具调用
                reply = ""
                tools_used = []
                token_usage = TokenUsage()

                for msg in result.get("messages", []):
                    if hasattr(msg, "type"):
                        if msg.type == "ai" and msg.content:
                            reply = msg.content
                        if msg.type == "ai" and hasattr(msg, "tool_calls"):
                            for tc in msg.tool_calls:
                                tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                                if tool_name and tool_name not in tools_used:
                                    tools_used.append(tool_name)

                # 尝试提取 usage
                for msg in reversed(result.get("messages", [])):
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        usage = msg.usage_metadata
                        token_usage.input_tokens = usage.get("input_tokens", 0)
                        token_usage.output_tokens = usage.get("output_tokens", 0)
                        token_usage.total_tokens = usage.get("total_tokens", 0)
                        break

                if not reply:
                    reply = "抱歉，我暂时无法回答这个问题。"

                # 检测情绪升级标记
                escalate = "[ESCALATE]" in reply
                if escalate:
                    reply = reply.replace("[ESCALATE]", "").strip()

                # 更新聊天历史
                self.chat_history.append(HumanMessage(content=user_message))
                self.chat_history.append(AIMessage(content=reply))

                if len(self.chat_history) > 40:
                    self.chat_history = self.chat_history[-40:]

                self._save()

                logger.info(
                    f"[Agent] session={self.session_id} tools={tools_used} "
                    f"tokens={token_usage.total_tokens} model={fallback.model_name} escalate={escalate}"
                )

                return {
                    "reply": reply,
                    "tools_used": tools_used,
                    "session_id": self.session_id,
                    "token_usage": token_usage.to_dict(),
                    "escalate": escalate,
                }

            except Exception as e:
                fallback.record_failure(e)
                retry_stats.record_error(e)

                # 如果还有备用模型可以尝试，继续循环
                if attempt == 0 and fallback.has_fallback:
                    logger.warning(f"[Agent] 主模型失败，切换到备用模型重试")
                    continue

                logger.error(f"[Agent] session={self.session_id} error: {e}", exc_info=True)
                return {
                    "reply": "抱歉，系统处理遇到问题，请稍后再试或联系人工客服。",
                    "tools_used": [],
                    "session_id": self.session_id,
                    "token_usage": TokenUsage().to_dict(),
                }

    async def chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        处理用户消息并以 SSE 流式返回（异步生成器）

        Yields:
            SSE 格式的事件字符串
        """
        fallback = get_fallback_llm()
        tokens_emitted = False

        for attempt in range(2):  # 最多尝试 2 次
            try:
                agent = get_agent(force_rebuild=(attempt > 0))
                messages = self._build_messages(user_message)

                retry_stats.record_call()

                reply = ""
                tools_used = []
                token_usage = TokenUsage()

                async for event in agent.astream_events({"messages": messages}, version="v2"):
                    kind = event.get("event", "")

                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            reply += chunk.content
                            tokens_emitted = True
                            yield _sse_event("token", {"content": chunk.content})

                    elif kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        if tool_name not in tools_used:
                            tools_used.append(tool_name)
                        yield _sse_event("tool_start", {"tool": tool_name})

                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        yield _sse_event("tool_end", {"tool": tool_name})

                    elif kind == "on_llm_end":
                        output = event.get("data", {}).get("output")
                        if output and hasattr(output, "usage_metadata") and output.usage_metadata:
                            usage = output.usage_metadata
                            token_usage.input_tokens = usage.get("input_tokens", 0)
                            token_usage.output_tokens = usage.get("output_tokens", 0)
                            token_usage.total_tokens = usage.get("total_tokens", 0)

                fallback.record_success()

                if not reply:
                    reply = "抱歉，我暂时无法回答这个问题。"

                # 检测情绪升级标记
                escalate = "[ESCALATE]" in reply
                if escalate:
                    reply = reply.replace("[ESCALATE]", "").strip()
                    yield _sse_event("escalate", {"reason": "用户情绪不满"})

                self.chat_history.append(HumanMessage(content=user_message))
                self.chat_history.append(AIMessage(content=reply))

                if len(self.chat_history) > 40:
                    self.chat_history = self.chat_history[-40:]

                self._save()

                logger.info(
                    f"[Agent Stream] session={self.session_id} tools={tools_used} "
                    f"tokens={token_usage.total_tokens} model={fallback.model_name} escalate={escalate}"
                )

                yield _sse_event("done", {
                    "reply": reply,
                    "tools_used": tools_used,
                    "session_id": self.session_id,
                    "token_usage": token_usage.to_dict(),
                    "escalate": escalate,
                })
                return  # 成功，退出

            except Exception as e:
                fallback.record_failure(e)
                retry_stats.record_error(e)

                # 如果已经开始输出 token，不能重试（用户已看到部分回复）
                if tokens_emitted:
                    logger.error(f"[Agent Stream] 流式输出中断: {e}", exc_info=True)
                    yield _sse_event("error", {
                        "message": "抱歉，回复过程中出现问题，请重新发送。",
                    })
                    return

                # 还没输出任何 token，可以尝试备用模型
                if attempt == 0 and fallback.has_fallback:
                    logger.warning(f"[Agent Stream] 主模型失败，切换到备用模型重试")
                    continue

                logger.error(f"[Agent Stream] session={self.session_id} error: {e}", exc_info=True)
                yield _sse_event("error", {
                    "message": "抱歉，系统处理遇到问题，请稍后再试或联系人工客服。",
                })

    def clear_history(self):
        """清空聊天历史"""
        self.chat_history = []
        self._save()


# ========== 会话管理器 ==========
class SessionManager:
    """管理多个聊天会话"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self):
        """从磁盘加载所有已有会话"""
        loaded = 0
        for f in SESSIONS_DIR.glob("*.json"):
            session = ChatSession._from_file(f)
            if session:
                self.sessions[session.session_id] = session
                loaded += 1
        if loaded:
            logger.info(f"[SessionManager] 从磁盘加载了 {loaded} 个会话")

    def get_session(self, session_id: str) -> ChatSession:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession(session_id)
        return self.sessions[session_id]

    def remove_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            path = SESSIONS_DIR / f"{session_id}.json"
            if path.exists():
                path.unlink()

    def list_sessions(self) -> List[str]:
        """列出所有会话ID"""
        return list(self.sessions.keys())


# 全局会话管理器
session_manager = SessionManager()


if __name__ == "__main__":
    session = ChatSession("test_session")
    print("服装电商智能客服已启动，输入 'quit' 退出\n")

    while True:
        user_input = input("用户: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        result = session.chat(user_input)
        print(f"\n客服: {result['reply']}")
        if result["tools_used"]:
            print(f"[使用的工具: {', '.join(result['tools_used'])}]")
        if result.get("token_usage"):
            t = result["token_usage"]
            print(f"[Token: {t['total_tokens']} (输入:{t['input_tokens']} 输出:{t['output_tokens']})]")
        print()
