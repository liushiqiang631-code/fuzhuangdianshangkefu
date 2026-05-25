"""
RAG 问答链模块 (LCEL)
基于 LangChain LCEL 构建 RAG 检索问答链
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from config import settings
from retriever import get_retriever


def format_docs(docs) -> str:
    """将检索到的文档格式化为字符串"""
    if not docs:
        return "未找到相关知识。"
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知来源")
        formatted.append(f"[文档{i}] (来源: {source})\n{doc.page_content}")
    return "\n\n".join(formatted)


def build_rag_chain():
    """
    构建 RAG 问答链 (LCEL)

    流程: 用户问题 -> 检索相关文档 -> 拼接上下文 -> LLM 生成回答
    """
    # LLM 实例
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_API_BASE,
    )

    # RAG 提示模板
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是服装电商智能客服。根据以下检索到的知识库内容回答用户问题。

规则：
1. 只基于提供的上下文回答，不要编造信息
2. 如果上下文中没有相关信息，诚实告知
3. 回答要简洁、准确、友好
4. 涉及商品信息时，引用具体的商品名称和数据
5. 如果是退换货问题，引用政策原文

检索到的相关知识：
{context}"""),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{question}"),
    ])

    # 获取检索器
    retriever_obj = get_retriever()
    retriever = retriever_obj.get_retriever()

    # LCEL 链: 检索 -> 格式化 -> 提示 -> LLM -> 解析
    rag_chain = (
        {
            "context": RunnablePassthrough.assign(
                docs=lambda x: retriever.invoke(str(x.get("question", x))) if isinstance(x, dict) else retriever.invoke(str(x))
            ) | RunnableLambda(lambda x: format_docs(x["docs"])),
            "question": RunnableLambda(lambda x: x["question"] if isinstance(x, dict) else str(x)),
            "chat_history": RunnableLambda(lambda x: x.get("chat_history", []) if isinstance(x, dict) else []),
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )

    # 包装为接受 dict 输入的链
    def run_rag(input_data):
        if isinstance(input_data, str):
            input_data = {"question": input_data, "chat_history": []}
        return rag_chain.invoke(input_data)

    return run_rag


def build_rag_chain_with_sources():
    """
    构建带来源引用的 RAG 链
    返回: (answer, sources)
    """
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_API_BASE,
    )

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是服装电商智能客服。根据以下检索到的知识库内容回答用户问题。

规则：
1. 只基于提供的上下文回答，不要编造信息
2. 如果上下文中没有相关信息，诚实告知
3. 回答要简洁、准确、友好

检索到的相关知识：
{context}"""),
        ("human", "{question}"),
    ])

    retriever_obj = get_retriever()

    def retrieve_and_format(query: str):
        docs = retriever_obj.search(query)
        context = format_docs(docs)
        sources = [
            {
                "content": doc.page_content[:200],
                "source": doc.metadata.get("source", "未知"),
            }
            for doc in docs
        ]
        return {"context": context, "sources": sources}

    def rag_with_sources(query: str):
        retrieved = retrieve_and_format(query)
        chain = rag_prompt | llm | StrOutputParser()
        answer = chain.invoke({
            "context": retrieved["context"],
            "question": query,
        })
        return {"answer": answer, "sources": retrieved["sources"]}

    return rag_with_sources


# ========== RAG 链单例 ==========
_rag_chain = None
_rag_chain_with_sources = None


def get_rag_chain():
    """获取 RAG 链单例"""
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = build_rag_chain()
    return _rag_chain


def get_rag_chain_with_sources():
    """获取带来源的 RAG 链单例"""
    global _rag_chain_with_sources
    if _rag_chain_with_sources is None:
        _rag_chain_with_sources = build_rag_chain_with_sources()
    return _rag_chain_with_sources


# ========== 简单 RAG 调用（单轮） ==========
def rag_query(question: str, chat_history: list = None) -> str:
    """简单的 RAG 查询接口"""
    chain = get_rag_chain()
    result = chain({"question": question, "chat_history": chat_history or []})
    return result


if __name__ == "__main__":
    # 测试 RAG 链
    test_questions = [
        "有什么纯棉T恤推荐？",
        "如何退换货？",
        "牛仔裤有哪些尺码？",
    ]
    for q in test_questions:
        print(f"\n问题: {q}")
        print(f"回答: {rag_query(q)}")
        print("-" * 50)
