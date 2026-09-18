"""
知识库管理 API 路由
支持文档上传、编辑、删除、同步
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from datetime import datetime
from config import settings

logger = logging.getLogger("zhice-platform.knowledge")

router = APIRouter(prefix="/admin/knowledge", tags=["知识库管理"])

DOCS_DIR = Path(settings.DATA_DOCS_DIR).resolve()
CHROMA_DIR = Path(settings.CHROMA_PERSIST_DIR)

# 允许的知识文档类型（与 ingest.py 支持的格式一致）
ALLOWED_DOC_EXTS = {".txt", ".md", ".json", ".csv"}

# 文档名白名单：字母数字下划线短横线中文点，防止路径穿越
import re
DOC_NAME_RE = re.compile(r"^[\w.\-\u4e00-\u9fa5]{1,100}$")


def _safe_docs_path(name: str) -> Path:
    """
    校验文档名并返回 DOCS_DIR 内的安全路径。
    防止 `..\\..\\x` / `../../x` 等路径穿越读写删任意文件。
    """
    if not name or not DOC_NAME_RE.fullmatch(name) or ".." in name:
        raise HTTPException(status_code=400, detail="文档名格式不正确")
    filepath = (DOCS_DIR / name).resolve()
    if not filepath.is_relative_to(DOCS_DIR):
        raise HTTPException(status_code=400, detail="文档名格式不正确")
    return filepath


class DocumentCreate(BaseModel):
    """创建文档请求"""
    name: str = Field(..., description="文档名称")
    type: str = Field("faq", description="文档类型：faq/product/policy/guide")
    content: str = Field(..., description="文档内容")


class DocumentUpdate(BaseModel):
    """更新文档请求"""
    content: str = Field(..., description="文档内容")


@router.get("/stats")
def get_stats():
    """获取知识库统计信息"""
    try:
        # 统计文档数量
        docs = list(DOCS_DIR.glob("*")) if DOCS_DIR.exists() else []
        total_docs = len([d for d in docs if d.is_file()])

        # 统计文件大小
        total_size = sum(d.stat().st_size for d in docs if d.is_file())

        # 统计 ChromaDB 大小
        db_size = 0
        if CHROMA_DIR.exists():
            for f in CHROMA_DIR.rglob("*"):
                if f.is_file():
                    db_size += f.stat().st_size

        # 统计片段数（直接查 ChromaDB 集合，不加载 Embedding 模型）
        total_chunks = 0
        try:
            import chromadb
            client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            collection = client.get_collection(settings.CHROMA_COLLECTION_NAME)
            total_chunks = collection.count()
        except Exception as e:
            logger.warning(f"[Knowledge] 获取片段数失败: {e}")

        return {
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "total_size": total_size,
            "db_size": db_size,
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        logger.error(f"[Knowledge] 获取统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.get("/documents")
def list_documents():
    """列出所有文档"""
    try:
        if not DOCS_DIR.exists():
            return {"documents": []}

        documents = []
        for f in sorted(DOCS_DIR.iterdir()):
            if f.is_file():
                # 统计片段数（简单估算）
                content = f.read_text(encoding="utf-8", errors="ignore")
                chunks = max(1, len(content) // 500)

                documents.append({
                    "name": f.name,
                    "type": _get_doc_type(f.name),
                    "size": f.stat().st_size,
                    "chunks": chunks,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

        return {"documents": documents}
    except Exception as e:
        logger.error(f"[Knowledge] 列出文档失败: {e}")
        raise HTTPException(status_code=500, detail="获取文档列表失败")


@router.get("/documents/{name}")
def get_document(name: str):
    """获取文档内容"""
    try:
        filepath = _safe_docs_path(name)
        if not filepath.is_file():
            raise HTTPException(status_code=404, detail="文档不存在")

        content = filepath.read_text(encoding="utf-8")

        return {
            "name": name,
            "content": content,
            "size": filepath.stat().st_size,
            "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Knowledge] 获取文档失败: {e}")
        raise HTTPException(status_code=500, detail="获取文档内容失败")


@router.post("/documents")
def create_document(doc: DocumentCreate):
    """创建新文档（同名文档已存在时拒绝，防止静默覆盖污染知识库）"""
    try:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # 清理文件名
        safe_name = "".join(c for c in doc.name if c.isalnum() or c in "-_.")
        if not safe_name:
            safe_name = f"doc-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 确保有扩展名
        if not any(safe_name.endswith(ext) for ext in ALLOWED_DOC_EXTS):
            safe_name += '.md'

        filepath = (DOCS_DIR / safe_name).resolve()
        if not filepath.is_relative_to(DOCS_DIR):
            raise HTTPException(status_code=400, detail="文档名格式不正确")

        if filepath.exists():
            raise HTTPException(status_code=409, detail=f"文档 {safe_name} 已存在，请换个名称或直接编辑该文档")

        # 写入文件
        filepath.write_text(doc.content, encoding="utf-8")

        logger.info(f"[Knowledge] 创建文档: {safe_name}")

        return {
            "message": f"文档 {safe_name} 创建成功",
            "name": safe_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Knowledge] 创建文档失败: {e}")
        raise HTTPException(status_code=500, detail="创建文档失败")


@router.put("/documents/{name}")
def update_document(name: str, update: DocumentUpdate):
    """更新文档内容"""
    try:
        filepath = _safe_docs_path(name)
        if not filepath.is_file():
            raise HTTPException(status_code=404, detail="文档不存在")

        filepath.write_text(update.content, encoding="utf-8")

        logger.info(f"[Knowledge] 更新文档: {name}")

        return {"message": f"文档 {name} 更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Knowledge] 更新文档失败: {e}")
        raise HTTPException(status_code=500, detail="更新文档失败")


@router.delete("/documents/{name}")
def delete_document(name: str):
    """删除文档"""
    try:
        filepath = _safe_docs_path(name)
        if not filepath.is_file():
            raise HTTPException(status_code=404, detail="文档不存在")

        filepath.unlink()

        logger.info(f"[Knowledge] 删除文档: {name}")

        return {"message": f"文档 {name} 删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Knowledge] 删除文档失败: {e}")
        raise HTTPException(status_code=500, detail="删除文档失败")


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档（分块读取限制大小，防止超大包占满内存）"""
    try:
        file_ext = Path(file.filename or "").suffix.lower()

        if file_ext not in ALLOWED_DOC_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_ext}，支持: {', '.join(sorted(ALLOWED_DOC_EXTS))}"
            )

        # 分块读取并限制大小（10MB）
        max_size = 10 * 1024 * 1024
        chunks = []
        total = 0
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")
            chunks.append(chunk)
        content = b"".join(chunks)

        # 保存文件
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # 清理文件名
        safe_name = "".join(c for c in file.filename if c.isalnum() or c in "-_.")
        if not safe_name:
            raise HTTPException(status_code=400, detail="文件名不合法")
        filepath = (DOCS_DIR / safe_name).resolve()
        if not filepath.is_relative_to(DOCS_DIR):
            raise HTTPException(status_code=400, detail="文件名不合法")

        # 如果文件已存在，添加时间戳
        if filepath.exists():
            name_part = Path(safe_name).stem
            ext_part = Path(safe_name).suffix
            safe_name = f"{name_part}-{datetime.now().strftime('%Y%m%d%H%M%S')}{ext_part}"
            filepath = (DOCS_DIR / safe_name).resolve()

        filepath.write_bytes(content)

        logger.info(f"[Knowledge] 上传文档: {safe_name} ({len(content)} bytes)")

        return {
            "message": f"文件 {safe_name} 上传成功",
            "name": safe_name,
            "size": len(content),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Knowledge] 上传文档失败: {e}")
        raise HTTPException(status_code=500, detail="上传文档失败")


@router.post("/sync")
def sync_database():
    """同步知识库到向量数据库（导入前清空旧索引，避免重复入库）"""
    try:
        from ingest import ingest_pipeline

        logger.info("[Knowledge] 开始同步知识库...")
        vectorstore = ingest_pipeline()

        if vectorstore is None:
            return {"message": "没有找到文档，跳过同步", "status": "warning"}

        logger.info("[Knowledge] 知识库同步完成")

        return {"message": "知识库同步完成", "status": "success"}
    except Exception as e:
        logger.error(f"[Knowledge] 同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


def _get_doc_type(filename: str) -> str:
    """根据文件名推断文档类型"""
    name_lower = filename.lower()
    if 'faq' in name_lower:
        return 'FAQ'
    if 'product' in name_lower or '商品' in name_lower:
        return '商品'
    if 'policy' in name_lower or '政策' in name_lower or '退换' in name_lower:
        return '政策'
    if 'guide' in name_lower or '指南' in name_lower:
        return '指南'
    return '其他'
