"""
知识库检索工具
Agent 可调用此工具从知识库中检索信息
"""
from langchain_core.tools import tool
from retriever import get_retriever
from config import settings
from cache import tool_cache


def _trim(text: str) -> str:
    """裁剪过大的工具结果，防止撑爆上下文"""
    limit = settings.MAX_TOOL_RESULT_CHARS
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[结果已截断，原始长度 {len(text)} 字符]"


@tool
def knowledge_search(query: str) -> str:
    """搜索服装商品知识库，查询商品信息、尺码、材质、搭配建议、退换货政策等。
    当用户询问商品详情、尺码推荐、穿搭建议、退换货规则等问题时使用此工具。

    Args:
        query: 搜索关键词或问题
    """
    # 查询缓存
    cached = tool_cache.get("knowledge_search", query)
    if cached:
        return cached

    try:
        retriever = get_retriever()
        docs = retriever.search(query, top_k=3)

        if not docs:
            return "未找到相关知识，建议用户联系人工客服获取帮助。"

        results = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "未知来源")
            results.append(f"[结果{i}] (来源: {source})\n{doc.page_content}")

        result = _trim("\n\n".join(results))
        tool_cache.set("knowledge_search", result, query)
        return result
    except Exception as e:
        return f"知识库检索出错: {str(e)}"


@tool
def get_product_info(product_name: str) -> str:
    """根据商品名称查询商品详细信息，包括价格、材质、颜色、尺码等。

    Args:
        product_name: 商品名称或关键词（如"T恤"、"牛仔裤"、"羽绒服"等）
    """
    # 查询缓存
    cached = tool_cache.get("get_product_info", product_name)
    if cached:
        return cached

    try:
        retriever = get_retriever()
        docs = retriever.search(f"商品 {product_name} 价格 材质 尺码", top_k=3)

        if not docs:
            return f"未找到商品「{product_name}」的信息，建议用户浏览商品列表或联系客服。"

        result = _trim("\n\n".join([doc.page_content for doc in docs]))
        tool_cache.set("get_product_info", result, product_name)
        return result
    except Exception as e:
        return f"查询商品信息出错: {str(e)}"
