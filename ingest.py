"""
数据导入与向量化模块
负责加载文档、分块、向量化并存入 ChromaDB
"""
import os
import json
from pathlib import Path
from typing import List, Optional
from langchain_community.document_loaders import (
    DirectoryLoader,
    TextLoader,
    JSONLoader,
    CSVLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from config import settings


def get_embeddings():
    """获取 Embedding 模型实例"""
    if settings.EMBEDDING_PROVIDER == "huggingface":
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings
        return HuggingFaceBgeEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    else:
        return OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
        )


def load_documents(docs_dir: Optional[str] = None) -> List:
    """
    从指定目录加载所有文档
    支持: .txt, .md, .json, .csv
    """
    docs_path = docs_dir or settings.DATA_DOCS_DIR
    if not os.path.exists(docs_path):
        os.makedirs(docs_path, exist_ok=True)
        print(f"[ingest] 文档目录不存在，已创建: {docs_path}")
        return []

    all_documents = []

    # TXT 文件
    try:
        txt_loader = DirectoryLoader(
            docs_path, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}
        )
        all_documents.extend(txt_loader.load())
    except Exception as e:
        print(f"[ingest] 加载 TXT 失败: {e}")

    # Markdown 文件 (用 TextLoader 读取)
    try:
        md_loader = DirectoryLoader(
            docs_path, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}
        )
        all_documents.extend(md_loader.load())
    except Exception as e:
        print(f"[ingest] 加载 Markdown 失败: {e}")

    # JSON 文件
    try:
        json_files = list(Path(docs_path).rglob("*.json"))
        for jf in json_files:
            try:
                loader = JSONLoader(
                    file_path=str(jf),
                    jq_schema=".[]",
                    text_content=False,
                )
                all_documents.extend(loader.load())
            except Exception:
                # 尝试整体加载
                loader = JSONLoader(
                    file_path=str(jf),
                    jq_schema=".",
                    text_content=False,
                )
                all_documents.extend(loader.load())
    except Exception as e:
        print(f"[ingest] 加载 JSON 失败: {e}")

    # CSV 文件
    try:
        csv_files = list(Path(docs_path).rglob("*.csv"))
        for cf in csv_files:
            loader = CSVLoader(file_path=str(cf), encoding="utf-8")
            all_documents.extend(loader.load())
    except Exception as e:
        print(f"[ingest] 加载 CSV 失败: {e}")

    print(f"[ingest] 共加载 {len(all_documents)} 个文档片段")
    return all_documents


def split_documents(documents: List, chunk_size: int = None, chunk_overlap: int = None) -> List:
    """将文档切分为更小的块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.RAG_CHUNK_SIZE,
        chunk_overlap=chunk_overlap or settings.RAG_CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"[ingest] 分块完成: {len(documents)} 个文档 -> {len(chunks)} 个块")
    return chunks


def create_vectorstore(chunks: List, persist_dir: Optional[str] = None) -> Chroma:
    """将文档块向量化并存入 ChromaDB"""
    embeddings = get_embeddings()
    persist_path = persist_dir or settings.CHROMA_PERSIST_DIR

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_path,
        collection_name=settings.CHROMA_COLLECTION_NAME,
    )
    print(f"[ingest] 向量数据库已创建/更新: {persist_path}")
    return vectorstore


def get_vectorstore(persist_dir: Optional[str] = None) -> Chroma:
    """获取已有的向量数据库实例"""
    embeddings = get_embeddings()
    persist_path = persist_dir or settings.CHROMA_PERSIST_DIR

    vectorstore = Chroma(
        embedding_function=embeddings,
        persist_directory=persist_path,
        collection_name=settings.CHROMA_COLLECTION_NAME,
    )
    return vectorstore


def ingest_pipeline(docs_dir: Optional[str] = None) -> Chroma:
    """完整的数据导入流水线: 加载 -> 分块 -> 向量化"""
    print("=" * 50)
    print("[ingest] 开始数据导入流水线...")
    print("=" * 50)

    # 1. 加载文档
    documents = load_documents(docs_dir)
    if not documents:
        print("[ingest] 没有找到文档，请将文档放入 data/docs/ 目录")
        return None

    # 2. 分块
    chunks = split_documents(documents)

    # 3. 向量化
    vectorstore = create_vectorstore(chunks)

    print("=" * 50)
    print(f"[ingest] 流水线完成! 共处理 {len(chunks)} 个文档块")
    print("=" * 50)
    return vectorstore


# ========== 示例数据生成 ==========
def generate_sample_data():
    """生成服装电商的示例知识文档"""
    docs_dir = settings.DATA_DOCS_DIR
    os.makedirs(docs_dir, exist_ok=True)

    # 商品信息
    products = [
        {
            "id": "P001",
            "name": "经典纯棉T恤",
            "category": "上装/T恤",
            "price": 89.00,
            "material": "100%新疆长绒棉",
            "colors": ["白色", "黑色", "灰色", "藏青色"],
            "sizes": ["S", "M", "L", "XL", "XXL"],
            "description": "采用新疆长绒棉，亲肤透气，经典圆领设计，适合日常穿着。",
            "size_chart": {"S": "胸围92cm 衣长66cm", "M": "胸围98cm 衣长68cm", "L": "胸围104cm 衣长70cm", "XL": "胸围110cm 衣长72cm", "XXL": "胸围116cm 衣长74cm"},
            "care_instructions": "可机洗，水温不超过30°C，不可漂白，低温熨烫",
        },
        {
            "id": "P002",
            "name": "修身牛仔裤",
            "category": "下装/牛仔裤",
            "price": 259.00,
            "material": "98%棉 2%氨纶",
            "colors": ["深蓝色", "浅蓝色", "黑色"],
            "sizes": ["28", "29", "30", "31", "32", "33", "34"],
            "description": "修身版型，微弹面料，经典五袋设计，百搭款式。",
            "size_chart": {"28": "腰围71cm 臀围90cm 裤长100cm", "30": "腰围76cm 臀围95cm 裤长102cm", "32": "腰围81cm 臀围100cm 裤长104cm", "34": "腰围86cm 臀围105cm 裤长106cm"},
            "care_instructions": "反面洗涤，冷水手洗或机洗，不可漂白",
        },
        {
            "id": "P003",
            "name": "轻薄羽绒服",
            "category": "外套/羽绒服",
            "price": 599.00,
            "material": "面料:100%涤纶 填充:90%白鸭绒",
            "colors": ["黑色", "藏青色", "军绿色", "卡其色"],
            "sizes": ["M", "L", "XL", "XXL"],
            "description": "轻薄保暖，90%白鸭绒填充，立领设计，可收纳折叠，方便携带。",
            "size_chart": {"M": "胸围108cm 衣长68cm", "L": "胸围114cm 衣长70cm", "XL": "胸围120cm 衣长72cm", "XXL": "胸围126cm 衣长74cm"},
            "care_instructions": "建议干洗，如水洗请使用中性洗涤剂，不可拧干",
        },
        {
            "id": "P004",
            "name": "碎花连衣裙",
            "category": "裙装/连衣裙",
            "price": 329.00,
            "material": "100%雪纺",
            "colors": ["花色A", "花色B", "花色C"],
            "sizes": ["S", "M", "L", "XL"],
            "description": "法式碎花设计，V领收腰，A字裙摆，优雅浪漫，适合春夏穿着。",
            "size_chart": {"S": "胸围84cm 腰围66cm 裙长110cm", "M": "胸围88cm 腰围70cm 裙长112cm", "L": "胸围92cm 腰围74cm 裙长114cm", "XL": "胸围96cm 腰围78cm 裙长116cm"},
            "care_instructions": "手洗推荐，冷水洗涤，不可漂白，阴凉处晾干",
        },
        {
            "id": "P005",
            "name": "运动卫衣",
            "category": "上装/卫衣",
            "price": 199.00,
            "material": "80%棉 20%涤纶",
            "colors": ["黑色", "灰色", "白色", "粉色"],
            "sizes": ["S", "M", "L", "XL", "XXL"],
            "description": "宽松版型，加绒内里，连帽设计，适合秋冬运动休闲穿着。",
            "size_chart": {"S": "胸围106cm 衣长67cm", "M": "胸围112cm 衣长69cm", "L": "胸围118cm 衣长71cm", "XL": "胸围124cm 衣长73cm"},
            "care_instructions": "可机洗，水温不超过30°C，不可漂白",
        },
    ]

    with open(os.path.join(docs_dir, "products.json"), "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # FAQ 常见问题
    faq = [
        {"question": "如何选择合适的尺码？", "answer": "请参考商品详情页的尺码表，根据您的身高、体重、胸围、腰围等数据选择。如果您在两个尺码之间，建议选大一号。如有疑问可咨询客服获取个性化建议。"},
        {"question": "支持哪些付款方式？", "answer": "我们支持微信支付、支付宝、银行卡、信用卡、花呗分期等多种付款方式。"},
        {"question": "发货时效是多久？", "answer": "普通商品下单后48小时内发货，预售商品会标注预计发货时间。节假日可能有所延迟，请谅解。"},
        {"question": "可以修改订单吗？", "answer": "未发货订单可以修改收货地址和联系方式，请在订单详情页操作或联系客服。已发货订单无法修改，可收货后申请退换。"},
        {"question": "如何申请退换货？", "answer": "收到商品后7天内，在商品未穿着、未洗涤、吊牌完好的情况下，可在订单详情页申请退换货。退换货需提供商品照片作为凭证。"},
        {"question": "退换货运费谁承担？", "answer": "因质量问题退换货，运费由我们承担；非质量问题（如尺码不合适、不喜欢等）退换货运费由买家承担。"},
        {"question": "退款多久到账？", "answer": "退货商品验收合格后，退款将在1-3个工作日内原路返回。支付宝/微信一般即时到账，银行卡可能需要3-5个工作日。"},
        {"question": "会员有什么权益？", "answer": "注册即为普通会员，消费满500元升级银卡会员（9.5折），满2000元升级金卡会员（9折），满5000元升级钻石会员（8.5折）。会员还享受生日礼券、优先发货、专属客服等权益。"},
        {"question": "有哪些优惠活动？", "answer": "我们定期举办满减活动（满200减30、满500减80）、新客首单9折、季节清仓特惠、会员日专属折扣等。请关注我们的公众号获取最新优惠信息。"},
        {"question": "商品有色差怎么办？", "answer": "由于拍摄光线和显示器色差，实物颜色可能与图片略有差异，属正常范围。如色差严重影响穿着，可在7天内申请退换货。"},
    ]

    with open(os.path.join(docs_dir, "faq.json"), "w", encoding="utf-8") as f:
        json.dump(faq, f, ensure_ascii=False, indent=2)

    # 退换货政策
    policy = """
# 退换货政策

## 一、退换货条件
1. 自签收之日起7天内可申请退换货
2. 商品须保持原样：未穿着、未洗涤、未修改，吊牌和包装完好
3. 赠品需一并退回
4. 定制商品、贴身衣物（内衣、泳装）不支持无理由退换

## 二、退换货流程
1. 在"我的订单"中找到对应订单，点击"申请退换"
2. 选择退换原因，上传商品照片
3. 等待审核（1个工作日内）
4. 审核通过后，按指引寄回商品
5. 收到商品并验收合格后，1-3个工作日内退款

## 三、运费说明
- 质量问题：运费由商家承担，提供运费补偿
- 非质量问题：运费由买家承担
- 包邮商品退货需扣除原订单运费

## 四、退款方式
- 原路退回：退回至原支付账户
- 退款时效：验收后1-3个工作日
- 银行卡退款可能需额外3-5个工作日到账

## 五、特殊说明
- 大促期间（双11、618等）退换货处理时间可能延长至5个工作日
- 如遇争议，以商品实物照片和质检报告为准
- 恶意退换货（频繁退货、调包等）将被限制退换货权限
"""

    with open(os.path.join(docs_dir, "return_policy.md"), "w", encoding="utf-8") as f:
        f.write(policy)

    # 搭配建议
    styling = """
# 穿搭搭配指南

## 春季搭配
- 碎花连衣裙 + 针织开衫 + 单鞋：温柔淑女风
- 纯棉T恤 + 牛仔裤 + 运动鞋：休闲百搭
- 卫衣 + 工装裤 + 帆布鞋：街头潮流

## 夏季搭配
- T恤 + 短裤 + 凉鞋：清爽简约
- 碎花连衣裙 + 草编包 + 凉鞋：度假风
- POLO衫 + 休闲裤 + 乐福鞋：商务休闲

## 秋季搭配
- 卫衣 + 牛仔裤 + 运动鞋：舒适休闲
- 针织衫 + 半身裙 + 短靴：优雅知性
- 轻薄羽绒服 + 卫衣 + 牛仔裤：保暖实用

## 冬季搭配
- 羽绒服 + 毛衣 + 加绒裤 + 靴子：保暖至上
- 大衣 + 高领毛衣 + 阔腿裤 + 短靴：气场全开
- 卫衣 + 羽绒马甲 + 束脚裤 + 运动鞋：运动保暖

## 体型搭配建议
- 偏瘦：选择有层次感的叠穿，浅色系增加视觉丰满感
- 偏胖：选择V领、竖条纹，深色系更显瘦，避免过于宽松
- 娇小：高腰线是关键，选择短款上衣+高腰下装，拉长比例
- 高个子：可以尝试长款大衣、阔腿裤等大气款式
"""

    with open(os.path.join(docs_dir, "styling_guide.md"), "w", encoding="utf-8") as f:
        f.write(styling)

    print(f"[ingest] 示例数据已生成到 {docs_dir}/")
    print(f"  - products.json: {len(products)} 个商品")
    print(f"  - faq.json: {len(faq)} 条FAQ")
    print(f"  - return_policy.md: 退换货政策")
    print(f"  - styling_guide.md: 穿搭搭配指南")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        generate_sample_data()

    ingest_pipeline()
