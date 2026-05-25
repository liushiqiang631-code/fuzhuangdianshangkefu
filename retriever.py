"""
检索模块
封装 ChromaDB 向量检索器，提供统一的检索接口
"""
from typing import List, Optional, Tuple
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config import settings


class ClothingRetriever:
    """服装电商知识库检索器"""

    def __init__(self, persist_dir: Optional[str] = None):
        if settings.EMBEDDING_PROVIDER == "huggingface":
            from langchain_community.embeddings import HuggingFaceBgeEmbeddings
            self.embeddings = HuggingFaceBgeEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        else:
            self.embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_API_BASE,
            )
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.vectorstore = Chroma(
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
            collection_name=settings.CHROMA_COLLECTION_NAME,
        )
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": settings.CHROMA_TOP_K,
                "score_threshold": settings.RAG_SCORE_THRESHOLD,
            },
        )

    def search(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """检索相关文档"""
        if top_k:
            retriever = self.vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "k": top_k,
                    "score_threshold": settings.RAG_SCORE_THRESHOLD,
                },
            )
            return retriever.invoke(query)
        return self.retriever.invoke(query)

    def search_with_score(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        """带相似度分数的检索"""
        return self.vectorstore.similarity_search_with_relevance_scores(
            query, k=top_k, score_threshold=settings.RAG_SCORE_THRESHOLD
        )

    def get_retriever(self):
        """获取 LangChain Retriever 对象（用于链式调用）"""
        return self.retriever


# 全局检索器实例（延迟初始化）
_retriever_instance: Optional[ClothingRetriever] = None


def get_retriever() -> ClothingRetriever:
    """获取全局检索器实例"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = ClothingRetriever()
    return _retriever_instance
