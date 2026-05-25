"""
API 路由模块
定义所有 HTTP 接口
"""
import uuid
import json
import time
import logging
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from pathlib import Path
from agent import session_manager, ChatSession, check_llm_health
from rag_chain import rag_query, get_rag_chain_with_sources
from config import settings

logger = logging.getLogger("zhice-platform")

router = APIRouter()


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
    docs_dir: Optional[str] = Field(None, description="文档目录路径")
    generate_sample: bool = Field(False, description="是否生成示例数据")


class SystemStatus(BaseModel):
    """系统状态"""
    status: str
    version: str
    model: str
    sessions_count: int
    chroma_db_exists: bool


# ========== 路由定义 ==========

@router.get("/", tags=["首页"])
async def root():
    """前端首页"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@router.get("/ui", tags=["首页"])
async def ui():
    """前端页面入口"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@router.get("/health", tags=["首页"])
async def health():
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
async def health_llm():
    """LLM 连通性检查（发送极简请求验证 API 可用性）"""
    return check_llm_health()


@router.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(request: ChatRequest):
    """
    智能客服对话接口（阻塞模式，返回完整回复）

    - **message**: 用户发送的消息
    - **session_id**: 可选，会话ID（用于多轮对话），不传则自动创建
    - **use_agent**: 是否使用 Agent 模式（支持工具调用），默认 True
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())[:8]

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
    session_id = request.session_id or str(uuid.uuid4())[:8]
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
async def chat_rag_with_sources(request: ChatRequest):
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
            "session_id": request.session_id or str(uuid.uuid4())[:8],
        }
    except Exception as e:
        logger.error(f"[RAG Sources] error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.delete("/chat/{session_id}", tags=["对话"])
async def clear_session(session_id: str):
    """清空指定会话的聊天历史"""
    session = session_manager.get_session(session_id)
    if not session.chat_history:
        return {"message": f"会话 {session_id} 不存在或已为空", "session_id": session_id}
    session.clear_history()
    return {"message": f"会话 {session_id} 已清空", "session_id": session_id}


@router.get("/sessions", tags=["会话"])
async def list_sessions():
    """列出所有活跃会话"""
    sessions = session_manager.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@router.post("/ingest", tags=["数据管理"])
async def ingest_data(request: IngestRequest):
    """
    导入知识库数据

    - **generate_sample**: 生成示例数据（商品信息、FAQ、退换货政策等）
    - **docs_dir**: 自定义文档目录路径
    """
    try:
        from ingest import ingest_pipeline, generate_sample_data

        if request.generate_sample:
            generate_sample_data()

        vectorstore = ingest_pipeline(request.docs_dir)
        if vectorstore is None:
            return {"message": "没有找到文档，请先上传文档到 data/docs/ 目录", "status": "warning"}

        return {"message": "数据导入完成", "status": "success"}
    except Exception as e:
        logger.error(f"[Ingest] error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="数据导入失败，请检查服务日志")


@router.get("/tools", tags=["工具"])
async def list_tools():
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
async def list_memory():
    """列出所有跨会话记忆"""
    from memory import list_memories
    memories = list_memories()
    return {"memories": memories, "count": len(memories)}


@router.post("/memory", tags=["记忆"])
async def add_memory(request: MemoryRequest):
    """添加一条跨会话记忆"""
    from memory import save_memory
    success = save_memory(request.name, request.content, request.type)
    if success:
        return {"message": f"记忆 '{request.name}' 已保存", "status": "success"}
    raise HTTPException(status_code=500, detail="保存记忆失败")


@router.delete("/memory/{name}", tags=["记忆"])
async def delete_memory(name: str):
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
async def submit_feedback(request: FeedbackRequest):
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
async def submit_escalation(request: EscalateRequest):
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


@router.post("/upload", tags=["上传"])
async def upload_image(file: UploadFile = File(...)):
    """上传图片文件"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_ext = file.filename.split(".")[-1] if "." in (file.filename or "") else "jpg"
    ext = "".join(c for c in raw_ext if c.isalnum()).lower() or "jpg"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    filepath = UPLOAD_DIR / filename

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    filepath.write_bytes(content)
    return {"url": f"/uploads/{filename}", "filename": filename}


@router.get("/uploads/{filename}", tags=["上传"])
async def get_upload(filename: str):
    """获取已上传的文件"""
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(filepath)


# ========== 管理后台 API ==========

@router.get("/admin", tags=["管理后台"])
async def admin_page():
    """管理后台页面"""
    return FileResponse(Path(__file__).parent / "static" / "admin.html")


@router.get("/admin/sessions", tags=["管理后台"])
async def admin_sessions():
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
async def admin_session_detail(session_id: str):
    """获取单个会话详情"""
    filepath = Path(settings.DATA_SESSIONS_DIR) / f"{session_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="会话不存在")
    data = json.loads(filepath.read_text(encoding="utf-8"))
    return data


@router.get("/admin/feedback", tags=["管理后台"])
async def admin_feedback():
    """获取反馈统计"""
    from feedback import load_feedback_stats, load_recent_feedback
    stats = load_feedback_stats()
    recent = load_recent_feedback(limit=50)
    return {"stats": stats, "recent": recent}


@router.get("/admin/logs", tags=["管理后台"])
async def admin_logs(lines: int = 200):
    """获取最近 N 行日志"""
    log_path = Path(settings.LOG_FILE)
    if not log_path.exists():
        return {"logs": [], "total": 0}

    try:
        # 读取最后 N 行（高效，不加载整个文件）
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-min(lines, 1000):]
        return {"logs": [line.rstrip() for line in tail], "total": len(all_lines)}
    except Exception as e:
        logger.error(f"[Admin] 读取日志失败: {e}")
        return {"logs": [], "total": 0, "error": str(e)}
