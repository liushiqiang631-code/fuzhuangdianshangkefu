<div align="center">

# 服装电商智能客服系统

**基于 LangChain + RAG + Agent 的下一代智能客服**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-1.2+-green?logo=langchain&logoColor=white)](https://langchain.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*智能对话 · 知识库检索 · 订单查询 · 价格计算 · 管理后台*

</div>

---

## 核心亮点

| 特性 | 说明 |
|:---|:---|
| **智能对话** | 多轮对话 + 上下文记忆 + SSE 流式输出 |
| **RAG 知识库** | ChromaDB 向量检索 + 中文 BGE Embedding |
| **Agent 工具集** | 13 个工具覆盖商品、订单、价格、用户 |
| **多模型 Fallback** | 主/备模型自动切换，故障自动恢复 |
| **管理后台** | 会话管理、反馈统计、实时日志 |

---

## 功能展示

### 智能客服对话

```
用户：有没有200元以下的黑色T恤？

🤖 服装电商客服：好的，我来帮你搜索一下！

找到 3 件符合条件的商品：

【经典纯棉T恤】
  价格：¥89（原价¥119，省¥30）
  材质：100%新疆长绒棉
  颜色：白色、黑色、灰色、藏青色
  
【印花圆领长袖T恤】
  价格：¥129（原价¥179，省¥50）
  材质：95%棉 5%氨纶
  颜色：白色、黑色、灰色
```

### 工具调用

```
▶ 调用了 3 个工具

  ✓ 搜索商品
  ✓ 查询分类
  ✓ 查询知识库
```

---

## 快速开始

### 环境要求

- Python 3.9+
- 8GB+ 内存（Embedding 模型需要）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/zhice-platform.git
cd zhice-platform

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 4. 生成示例数据并导入向量库
python ingest.py --sample

# 5. 启动服务
python -m app.main
```

访问 http://localhost:8000 即可使用。

### Windows 一键启动

双击 `启动服务.bat` 自动启动服务并打开浏览器。

---

## 配置说明

### 环境变量 (.env)

```bash
# LLM 配置
OPENAI_API_KEY=sk-xxx          # DeepSeek API Key
OPENAI_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat        # 模型名称

# Embedding 配置
EMBEDDING_PROVIDER=huggingface  # 使用本地模型
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# ChromaDB 配置
CHROMA_PERSIST_DIR=./data/chroma_db
CHROMA_COLLECTION_NAME=clothing_ecommerce
```

### 多模型 Fallback

```bash
# 启用备用模型
LLM_FALLBACK_ENABLED=true
LLM_FALLBACK_MODEL=gpt-4o-mini
LLM_FALLBACK_API_KEY=sk-xxx
LLM_FALLBACK_API_BASE=https://api.openai.com/v1
LLM_FALLBACK_COOLDOWN=300  # 主模型冷却恢复时间（秒）
```

---

## 项目结构

```
zhice-platform/
├── config.py              # 全局配置（pydantic-settings）
├── ingest.py              # 数据导入与向量化
├── retriever.py           # 检索模块（ChromaDB 向量检索）
├── rag_chain.py           # RAG 问答链（LCEL）
├── agent.py               # Agent 构建与会话管理
├── llm_factory.py         # LLM 多模型 Fallback 工厂
├── cache.py               # 工具结果 TTL 缓存
├── retry.py               # LLM 调用重试机制
├── feedback.py            # 用户反馈存储
├── memory.py              # 跨会话记忆管理
├── tools/                 # Agent 工具集
│   ├── knowledge.py       # 知识库检索工具
│   ├── analytics.py       # 业务数据查询
│   ├── calculator.py      # 价格/折扣/满减计算
│   ├── user_activation.py # 用户激活/查询/推荐
│   └── product_search.py  # 结构化商品搜索
├── app/                   # Web 应用
│   ├── main.py            # FastAPI 应用入口
│   ├── routes.py          # API 路由
│   └── static/            # 前端静态文件
│       ├── index.html     # 客服聊天页面
│       ├── app.js         # 聊天前端逻辑
│       ├── styles.css     # 样式
│       ├── admin.html     # 管理后台页面
│       └── admin.js       # 管理后台逻辑
├── middleware/             # 中间件
│   └── auth.py            # 认证/日志/限流中间件
├── data/                  # 数据目录
│   ├── docs/              # 知识文档
│   ├── sessions/          # 会话持久化
│   ├── memory/            # 跨会话记忆
│   ├── uploads/           # 用户上传图片
│   └── chroma_db/         # 向量数据库
├── .env                   # 环境变量
├── requirements.txt       # 依赖列表
└── 启动服务.bat           # Windows 一键启动
```

---

## API 接口

### 对话接口

| 接口 | 方法 | 说明 |
|:---|:---:|:---|
| `/chat` | POST | 智能客服对话（阻塞模式） |
| `/chat/stream` | POST | 智能客服对话（SSE 流式） |
| `/chat/rag-with-sources` | POST | RAG 问答（带来源） |
| `/chat/{session_id}` | DELETE | 清空会话 |

### 数据接口

| 接口 | 方法 | 说明 |
|:---|:---:|:---|
| `/sessions` | GET | 列出活跃会话 |
| `/tools` | GET | 列出可用工具 |
| `/ingest` | POST | 导入知识库数据 |
| `/feedback` | POST | 提交对话反馈 |
| `/escalate` | POST | 记录转人工请求 |
| `/upload` | POST | 上传图片文件 |
| `/memory` | GET/POST | 跨会话记忆管理 |

### 管理接口

| 接口 | 方法 | 说明 |
|:---|:---:|:---|
| `/admin` | GET | 管理后台页面 |
| `/admin/sessions` | GET | 会话列表 |
| `/admin/sessions/{id}` | GET | 会话详情 |
| `/admin/feedback` | GET | 反馈统计 |
| `/admin/logs` | GET | 系统日志 |

### 健康检查

| 接口 | 方法 | 说明 |
|:---|:---:|:---|
| `/health` | GET | 系统状态 |
| `/health/llm` | GET | LLM 连通性检查 |

---

## 使用示例

### 智能客服对话

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "有什么纯棉T恤推荐？", "session_id": "user001"}'
```

### 查询订单

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我查一下订单 ORD20260430001 的物流信息"}'
```

### 价格计算

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "一件原价259的牛仔裤打8折，再用满200减30的券，最终多少钱？"}'
```

### 结构化商品搜索

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "有没有200元以下的黑色T恤？"}'
```

---

## 工具集

| 工具 | 功能 |
|:---|:---|
| `knowledge_search` | 知识库检索（向量搜索） |
| `get_product_info` | 商品信息查询 |
| `search_products` | 结构化商品搜索（按分类/价格/颜色/尺码过滤） |
| `list_categories` | 查询所有商品分类 |
| `query_order` | 订单查询 |
| `query_user_orders` | 用户订单列表 |
| `query_active_users` | 活跃用户/业务数据 |
| `calculate_price` | 价格计算 |
| `calculate_full_reduction` | 满减计算 |
| `calculate_member_discount` | 会员折扣计算 |
| `activate_user` | 用户激活 |
| `get_user_info` | 用户信息查询 |
| `recommend_for_user` | 个性化推荐 |

---

## 技术栈

| 类别 | 技术 |
|:---|:---|
| **AI 框架** | LangChain 1.2+ / LangGraph |
| **向量数据库** | ChromaDB |
| **Embedding** | BAAI/bge-small-zh-v1.5 |
| **Web 框架** | FastAPI |
| **配置管理** | Pydantic Settings |
| **前端渲染** | Marked.js (Markdown) |
| **LLM** | DeepSeek / OpenAI 兼容接口 |

---

## 知识库数据

系统内置以下知识文档：

- **商品信息** (products.json)：20 款服装商品，含价格、材质、尺码表
- **FAQ** (faq.json)：20 条常见问题解答
- **穿搭指南** (styling_guide.md)：四季穿搭建议、体型搭配、色彩搭配
- **尺码指南** (size_guide.md)：身体测量方法、男女尺码对照表
- **店铺介绍** (store_info.md)：品牌故事、会员体系、售后保障

---

## 管理后台

访问 `/admin` 进入管理后台，支持：

- **会话管理**：查看所有会话列表、对话详情
- **反馈统计**：好评率、好评/差评数量
- **系统日志**：实时查看应用日志，支持 ERROR/WARNING 高亮

---

## 部署说明

### 开发环境

```bash
python -m app.main
```

### 生产环境

```bash
# 使用 Gunicorn + Uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python ingest.py --sample

EXPOSE 8000
CMD ["python", "-m", "app.main"]
```

---

## 常见问题

### Q: 启动时报错 "No module named xxx"

A: 确保已安装所有依赖：`pip install -r requirements.txt`

### Q: Embedding 模型下载慢

A: 首次运行会自动下载 BGE 模型（约 100MB），可手动下载后放到 `~/.cache/huggingface/` 目录

### Q: ChromaDB 数据丢失

A: 向量数据库存储在 `data/chroma_db/`，删除该目录后需重新运行 `python ingest.py`

### Q: API Key 无效

A: 检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确，DeepSeek 需要在 [deepseek.com](https://deepseek.com) 申请

---

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

---

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果觉得有用，请点个 Star 支持一下！**

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/zhice-platform&type=Date)](https://star-history.com/#yourusername/zhice-platform&Date)

</div>
