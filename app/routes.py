"""
API 路由模块
定义所有 HTTP 接口
"""
import uuid
import json
import re
import time
import logging
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from pathlib import Path
from agent import session_manager, check_llm_health, is_valid_session_id, SESSIONS_DIR
from rag_chain import rag_query, get_rag_chain_with_sources
from config import settings

logger = logging.getLogger("zhice-platform")

router = APIRouter()

# 上传文件白名单：扩展名 -> (Content-Type, 文件头魔数)
ALLOWED_IMAGE_TYPES = {
    ".jpg": ("image/jpeg", [b"\xff\xd8\xff"]),
    ".jpeg": ("image/jpeg", [b"\xff\xd8\xff"]),
    ".png": ("image/png", [b"\x89PNG\r\n\x1a\n"]),
    ".gif": ("image/gif", [b"GIF87a", b"GIF89a"]),
    ".webp": ("image/webp", [b"RIFF"]),
}


# ========== 请求/响应模型 ==========
class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="会话ID，不传则自动创建")
    use_agent: bool = Field(True, description="是否使用 Agent 模式（带工具调用），否则使用纯 RAG")


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str = Field(..., description="客服回复")
    session_id: str = Field(..., description="会话ID")
    tools_used: Optional[List[str]] = Field(None, description="使用的工具列表")
    sources: Optional[List[Dict]] = Field(None, description="RAG 引用来源")
    token_usage: Optional[Dict] = Field(None, description="Token 用量")


class IngestRequest(BaseModel):
    """数据导入请求"""
    generate_sample: bool = Field(False, description="是否重新生成示例数据")


class SystemStatus(BaseModel):
    """系统状态"""
    status: str
    version: str
    model: str
    sessions_count: int
    chroma_db_exists: bool


def _require_session_id(session_id: Optional[str]) -> str:
    """校验并返回会话 ID（不传则生成完整 UUID）"""
    session_id = session_id or str(uuid.uuid4())
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确（仅允许字母、数字、下划线和短横线，最长64位）")
    return session_id


# ========== 路由定义 ==========

@router.get("/", tags=["首页"])
def root():
    """前端首页"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@router.get("/ui", tags=["首页"])
def ui():
    """前端页面入口"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@router.get("/knowledge", tags=["知识库管理"])
def knowledge_page():
    """知识库管理页面"""
    return FileResponse(Path(__file__).parent / "static" / "knowledge.html")


@router.get("/health", tags=["首页"])
def health():
    """健康检查接口"""
    chroma_exists = Path(settings.CHROMA_PERSIST_DIR).exists()
    return SystemStatus(
        status="healthy",
        version=settings.APP_VERSION,
        model=settings.LLM_MODEL,
        sessions_count=len(session_manager.sessions),
        chroma_db_exists=chroma_exists,
    )


@router.get("/health/llm", tags=["首页"])
def health_llm():
    """LLM 连通性检查（发送极简请求验证 API 可用性）"""
    return check_llm_health()


@router.post("/chat", response_model=ChatResponse, tags=["对话"])
def chat(request: ChatRequest):
    """
    智能客服对话接口（阻塞模式，返回完整回复）

    - **message**: 用户发送的消息
    - **session_id**: 可选，会话ID（用于多轮对话），不传则自动创建
    - **use_agent**: 是否使用 Agent 模式（支持工具调用），默认 True

    注意：这里刻意用同步 def（而非 async def），FastAPI 会将其放入线程池执行，
    避免 LLM 秒级阻塞调用卡死事件循环。
    """
    start_time = time.time()
    session_id = _require_session_id(request.session_id)

    try:
        if request.use_agent:
            session = session_manager.get_session(session_id)
            result = session.chat(request.message)
            elapsed = time.time() - start_time
            logger.info(f"[Chat] session={session_id} tools={result['tools_used']} time={elapsed:.2f}s")
            return ChatResponse(
                reply=result["reply"],
                session_id=session_id,
                tools_used=result["tools_used"],
                token_usage=result.get("token_usage"),
            )
        else:
            answer = rag_query(request.message)
            elapsed = time.time() - start_time
            logger.info(f"[RAG] session={session_id} time={elapsed:.2f}s")
            return ChatResponse(
                reply=answer,
                session_id=session_id,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Chat] session={session_id} error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.post("/chat/stream", tags=["对话"])
async def chat_stream(request: ChatRequest):
    """
    智能客服对话接口（SSE 流式模式，逐 token 返回）

    返回 text/event-stream 格式，事件类型：
    - token: 文本片段
    - tool_start: 工具开始调用
    - tool_end: 工具调用结束
    - done: 完成（包含完整回复和工具列表）
    - error: 错误
    """
    session_id = _require_session_id(request.session_id)
    session = session_manager.get_session(session_id)

    async def event_generator():
        # 先发送 session_id 事件
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        async for chunk in session.chat_stream(request.message):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/rag-with-sources", tags=["对话"])
def chat_rag_with_sources(request: ChatRequest):
    """
    RAG 问答（带来源引用）
    返回回答和检索到的知识库来源
    """
    try:
        rag_fn = get_rag_chain_with_sources()
        result = rag_fn(request.message)
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "session_id": request.session_id or str(uuid.uuid4()),
        }
    except Exception as e:
        logger.error(f"[RAG Sources] error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.delete("/chat/{session_id}", tags=["对话"])
def clear_session(session_id: str):
    """清空指定会话的聊天历史"""
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")
    if session_id not in session_manager.sessions:
        return {"message": f"会话 {session_id} 不存在", "session_id": session_id}
    session = session_manager.sessions[session_id]
    if not session.chat_history:
        return {"message": f"会话 {session_id} 已为空", "session_id": session_id}
    session.clear_history()
    return {"message": f"会话 {session_id} 已清空", "session_id": session_id}


@router.get("/sessions", tags=["会话"])
def list_sessions():
    """列出所有活跃会话"""
    sessions = session_manager.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@router.post("/ingest", tags=["数据管理"])
def ingest_data(request: IngestRequest):
    """
    导入知识库数据（固定从 data/docs/ 读取，导入前清空旧索引避免重复入库）

    - **generate_sample**: 重新生成示例数据
    """
    try:
        from ingest import ingest_pipeline, generate_sample_data

        if request.generate_sample:
            generate_sample_data()

        vectorstore = ingest_pipeline()
        if vectorstore is None:
            return {"message": "没有找到文档，请先上传文档到 data/docs/ 目录", "status": "warning"}

        return {"message": "数据导入完成", "status": "success"}
    except Exception as e:
        logger.error(f"[Ingest] error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="数据导入失败，请检查服务日志")


@router.get("/tools", tags=["工具"])
def list_tools():
    """列出所有可用的 Agent 工具"""
    from agent import AGENT_TOOLS
    tools_info = []
    for tool in AGENT_TOOLS:
        tools_info.append({
            "name": tool.name,
            "description": tool.description,
        })
    return {"tools": tools_info, "count": len(tools_info)}


# ========== 记忆管理 API ==========

class MemoryRequest(BaseModel):
    """添加记忆请求"""
    name: str = Field(..., description="记忆名称（kebab-case）", min_length=1, max_length=100)
    content: str = Field(..., description="记忆内容", min_length=1, max_length=2000)
    type: str = Field("user", description="记忆类型: user/feedback/project/reference")


@router.get("/memory", tags=["记忆"])
def list_memory():
    """列出所有跨会话记忆"""
    from memory import list_memories
    memories = list_memories()
    return {"memories": memories, "count": len(memories)}


@router.post("/memory", tags=["记忆"])
def add_memory(request: MemoryRequest):
    """添加一条跨会话记忆"""
    from memory import save_memory
    success = save_memory(request.name, request.content, request.type)
    if success:
        return {"message": f"记忆 '{request.name}' 已保存", "status": "success"}
    raise HTTPException(status_code=500, detail="保存记忆失败")


@router.delete("/memory/{name}", tags=["记忆"])
def delete_memory(name: str):
    """删除一条跨会话记忆"""
    from memory import delete_memory as del_mem
    success = del_mem(name)
    if success:
        return {"message": f"记忆 '{name}' 已删除", "status": "success"}
    raise HTTPException(status_code=404, detail=f"记忆 '{name}' 不存在")


# ========== 反馈 API ==========

class FeedbackRequest(BaseModel):
    """反馈请求"""
    session_id: str
    message_index: int = 0
    rating: str = Field(..., description="positive 或 negative")
    comment: str = ""


@router.post("/feedback", tags=["反馈"])
def submit_feedback(request: FeedbackRequest):
    """提交对话反馈"""
    from feedback import save_feedback
    success = save_feedback(request.session_id, request.message_index, request.rating, request.comment)
    if success:
        return {"message": "感谢您的反馈！", "status": "success"}
    raise HTTPException(status_code=500, detail="保存反馈失败")


# ========== 情绪升级 API ==========

class EscalateRequest(BaseModel):
    """转人工请求"""
    session_id: str
    reason: str = "用户情绪不满"


@router.post("/escalate", tags=["客服"])
def submit_escalation(request: EscalateRequest):
    """记录转人工请求"""
    try:
        data_dir = Path("./data")
        data_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "session_id": request.session_id,
            "reason": request.reason,
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(data_dir / "escalations.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"message": "已记录转人工请求", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="记录失败")


# ========== 图片上传 API ==========

UPLOAD_DIR = Path("./data/uploads")
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload", tags=["上传"])
async def upload_image(file: UploadFile = File(...)):
    """上传图片文件（校验扩展名、文件头魔数与大小，拒绝 SVG 等可执行内容）"""
    raw_name = file.filename or ""
    ext = Path(raw_name).suffix.lower()
    if ext not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="只支持 jpg/png/gif/webp 图片文件")

    content_type, magic_headers = ALLOWED_IMAGE_TYPES[ext]

    # 分块读取并限制大小，避免超大包占满内存
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")
        chunks.append(chunk)
    content = b"".join(chunks)

    # 文件头魔数校验（防止伪造扩展名上传 SVG/HTML 等内容）
    if not any(content.startswith(h) for h in magic_headers):
        raise HTTPException(status_code=400, detail="文件内容不是有效的图片")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)
    return {"url": f"/uploads/{filename}", "filename": filename}


@router.get("/uploads/{filename}", tags=["上传"])
def get_upload(filename: str):
    """获取已上传的文件（校验路径不越界）"""
    upload_root = UPLOAD_DIR.resolve()
    filepath = (UPLOAD_DIR / filename).resolve()
    if not filepath.is_relative_to(upload_root) or not filepath.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(filepath)


# ========== 管理后台 API ==========

@router.get("/admin", tags=["管理后台"])
def admin_page():
    """管理后台页面"""
    return FileResponse(Path(__file__).parent / "static" / "admin.html")


@router.get("/admin/sessions", tags=["管理后台"])
def admin_sessions():
    """获取所有会话列表（含摘要信息）"""
    sessions_dir = Path(settings.DATA_SESSIONS_DIR)
    if not sessions_dir.exists():
        return {"sessions": []}

    sessions = []
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            history = data.get("chat_history", [])
            # 提取第一条用户消息作为摘要
            first_user_msg = ""
            for msg in history:
                if msg.get("role") == "human":
                    first_user_msg = msg.get("content", "")[:60]
                    break
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "message_count": len(history),
                "first_message": first_user_msg,
                "created_at": data.get("created_at", 0),
                "last_active": data.get("last_active", 0),
            })
        except Exception:
            continue

    sessions.sort(key=lambda x: x.get("last_active", 0), reverse=True)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/admin/sessions/{session_id}", tags=["管理后台"])
def admin_session_detail(session_id: str):
    """获取单个会话详情"""
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")
    filepath = Path(settings.DATA_SESSIONS_DIR) / f"{session_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="会话不存在")
    data = json.loads(filepath.read_text(encoding="utf-8"))
    return data


@router.get("/admin/feedback", tags=["管理后台"])
def admin_feedback():
    """获取反馈统计"""
    from feedback import load_feedback_stats, load_recent_feedback
    stats = load_feedback_stats()
    recent = load_recent_feedback(limit=50)
    return {"stats": stats, "recent": recent}


@router.get("/admin/logs", tags=["管理后台"])
def admin_logs(lines: int = 200):
    """获取最近 N 行日志"""
    log_path = Path(settings.LOG_FILE)
    if not log_path.exists():
        return {"logs": [], "total": 0}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-min(lines, 1000):]
        return {"logs": [line.rstrip() for line in tail], "total": len(all_lines)}
    except Exception as e:
        logger.error(f"[Admin] 读取日志失败: {e}")
        return {"logs": [], "total": 0, "error": str(e)}


# ========== 对话搜索 API ==========

@router.get("/search", tags=["搜索"])
def search_conversations_api(query: str, limit: int = 20):
    """搜索历史对话"""
    from conversation_search import search_conversations
    results = search_conversations(query, limit)
    return {"results": results, "count": len(results)}


@router.get("/sessions/recent", tags=["会话"])
def get_recent_conversations(limit: int = 10):
    """获取最近的对话"""
    from conversation_search import conversation_searcher
    sessions = conversation_searcher.get_recent_conversations(limit)
    return {"sessions": sessions}


# ========== 对话分支 API ==========

@router.post("/branches", tags=["分支"])
def create_branch_api(
    session_id: str,
    fork_point: int,
    name: str = "",
):
    """创建对话分支"""
    from conversation_branch import branch_manager

    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")
    if fork_point < 0:
        raise HTTPException(status_code=400, detail="fork_point 不能为负数")
    if session_id not in session_manager.sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 转换消息格式
    messages = []
    for msg in session_manager.sessions[session_id].chat_history:
        if hasattr(msg, "content"):
            messages.append({
                "role": "human" if hasattr(msg, "type") and msg.type == "human" else "ai",
                "content": msg.content,
            })

    if fork_point >= len(messages):
        raise HTTPException(status_code=400, detail=f"fork_point 超出范围（当前会话共 {len(messages)} 条消息）")

    branch = branch_manager.create_branch(
        session_id=session_id,
        messages=messages,
        fork_point=fork_point,
        name=name,
    )

    return {
        "branch_id": branch.branch_id,
        "name": branch.name,
        "fork_point": branch.fork_point,
        "message_count": len(branch.messages),
    }


@router.get("/branches/{session_id}", tags=["分支"])
def get_session_branches(session_id: str):
    """获取会话的所有分支"""
    from conversation_branch import branch_manager
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")
    branches = branch_manager.get_session_branches(session_id)
    return {"branches": branches, "count": len(branches)}


@router.post("/branches/{branch_id}/switch", tags=["分支"])
def switch_to_branch(branch_id: str):
    """切换到指定分支（将会话历史回退到分支的 fork_point）"""
    from conversation_branch import branch_manager
    from agent import ChatSession, _deserialize_history

    branch = branch_manager.get_branch(branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="分支不存在")

    session = session_manager.get_session(branch.session_id)

    # 真正切换：用分支在 fork_point 处的消息覆盖会话历史
    cutoff = branch.fork_point + 1
    messages = branch.messages[:cutoff]
    history = _deserialize_history([
        {"role": m.get("role", "human"), "content": m.get("content", "")}
        for m in messages
    ])
    session.chat_history = history
    session._save()

    return {
        "branch_id": branch.branch_id,
        "session_id": branch.session_id,
        "fork_point": branch.fork_point,
        "message_count": len(session.chat_history),
        "messages": messages,
    }


# ========== 会话导出/导入 API ==========

@router.get("/sessions/{session_id}/export", tags=["会话"])
def export_session(session_id: str):
    """导出会话（直接读磁盘，包含运行中新建的会话）"""
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")
    # 先落盘内存中可能的未保存变更
    if session_id in session_manager.sessions:
        session_manager.sessions[session_id]._save()
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="会话不存在")
    return json.loads(filepath.read_text(encoding="utf-8"))


@router.post("/sessions/import", tags=["会话"])
def import_session(data: Dict):
    """导入会话（兼容 chat_history 与 messages 两种键名）"""
    session_id = data.get("session_id") or str(uuid.uuid4())
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")

    history = data.get("chat_history")
    if history is None:
        history = data.get("messages", [])
    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="消息格式不正确，需要 chat_history 数组")

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    file_data = {
        "session_id": session_id,
        "chat_history": history,
        "created_at": data.get("created_at", time.time()),
        "last_active": time.time(),
    }
    filepath = SESSIONS_DIR / f"{session_id}.json"
    filepath.write_text(json.dumps(file_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 加载进内存，让后续对话能接上导入的历史
    from agent import ChatSession
    session = ChatSession._from_file(filepath)
    if session:
        session_manager.sessions[session_id] = session

    return {"session_id": session_id, "message": "导入成功"}


# ========== 快捷回复 API ==========

@router.get("/quick-replies", tags=["交互"])
def get_quick_replies_api(category: str = "general"):
    """获取快捷回复"""
    from tools.recommendation import get_quick_replies
    replies = get_quick_replies(category)
    return {"replies": replies}
