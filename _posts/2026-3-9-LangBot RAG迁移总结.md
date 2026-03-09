---
title: "LangBot RAG 架构迁移：从内置实现到插件化引擎"
date: 2026-03-09
categories: [系统设计, 开源]
tags: [RAG, 插件架构, LangBot, 向量检索, 重构]
---

## 背景

[LangBot](https://github.com/langbot-app/LangBot) 是一个开源的 AI 对话机器人平台，支持接入多种 LLM、部署到多个即时通讯渠道。作为一个开源爱好者，我有幸参与了这个项目，并在其中主导和设计了一次比较大的架构改动：**把 RAG 能力从 LangBot 内置实现中完全剥离，迁移为插件化架构。**

这篇文章先简单聊聊 RAG 的基本概念，然后记录这次迁移的动机、设计思路、技术选型和踩过的坑，最后聊聊前沿 RAG 技术和未来方向。

---

## 1. RAG 是什么，以及它在 LangBot 中的角色

### 1.1 RAG 基本概念

RAG（Retrieval-Augmented Generation，检索增强生成）的核心思路很简单：**LLM 不知道的事情，先帮它查到，再让它回答。**

一个标准的 RAG 流程分两个阶段：

**入库阶段（Indexing）**——把知识变成可检索的形式：

```
原始文档 → 解析（Parser）→ 分块（Chunker）→ 向量化（Embedding）→ 存入向量数据库
```

- **解析**：把 PDF、Word、Markdown 等格式转成纯文本。听起来简单，实际上这一步经常是整条链路最脆弱的环节——PDF 的排版千奇百怪，表格、多栏、扫描件都是坑。
- **分块**：把长文档切成适合检索的小段。太长了 LLM 上下文装不下，太短了丢失语义上下文。常见策略有固定大小切分、按语义边界切分、按文档结构切分等。
- **向量化**：用 Embedding 模型把文本变成稠密向量。语义相近的文本在向量空间中距离也近，这是后续检索的基础。

**检索阶段（Retrieval）**——回答用户问题时实时查询：

```
用户提问 → 向量化 → 在向量库中搜相似内容 → 取 Top-K 结果 → 拼入 Prompt → LLM 生成回答
```

这就是所谓的"让 LLM 带着参考资料答题"。RAG 的价值在于：LLM 不需要在训练时见过这些知识，只要检索阶段能找到相关内容，就能给出准确回答。

### 1.2 RAG 在 LangBot 中的应用

LangBot 是一个 IM 机器人平台，用户把它部署在微信、QQ、飞书等渠道上，作为智能客服、知识助手来用。RAG 在这个场景下的作用是：用户上传自己的文档（产品手册、FAQ、规章制度等），机器人就能基于这些文档回答问题，而不是只靠 LLM 的通用知识。

这是 LangBot 的核心功能之一，也是这次重构的对象。

---

## 2. 为什么要动 RAG 这一层

LangBot 原来的 RAG 实现是"内置"的——解析、分块、向量化、检索全部写在核心代码里。同时还有一个"外置知识库"的概念，用来对接 Dify、FastGPT 这类第三方 RAG 平台。两套知识库在前端用 Tab 切换，后端用不同的表和接口。

我最初参与 LangBot 是为它增加了 SeekDB 向量数据库的支持，一个比较小的改动。后来想在 RAG 层面做更多事情——比如增加新的分块策略、支持查询改写——才发现内置实现的扩展性很差，改不动。和项目维护者（RockChinQ）讨论之后，我们决定不做修补，直接重构 RAG 架构，把业务逻辑从核心代码中剥离出来。

具体的问题有三个：

**1. 内置 RAG 策略太死。** 只有一种分块策略（固定大小递归切分），没有 Parent-Child 分块、没有 QA 对索引、没有查询改写。想加新策略就得改核心代码，发版周期长，社区贡献门槛高。

**2. 两套知识库并存增加了维护成本。** 内置和外置的数据模型不同（`KnowledgeBase` vs `ExternalKnowledgeBase`）、API 不同、前端组件不同。每次改一个功能要改两遍，容易漏。

**3. 外置知识库的"外置"太重了。** 用户想用 RAGFlow 的高级功能（GraphRAG、RAPTOR），需要单独部署一整套 RAGFlow 服务。对于只想加个知识库的轻量用户来说，门槛太高。

核心矛盾是：**LangBot 想同时满足"开箱即用"和"深度可定制"，但内置实现做不到后者，外置方案做不到前者。**

解决思路很直接——把 RAG 业务逻辑做成插件。LangBot 只管基础设施（模型、向量库、文件存储），具体的 RAG 策略由插件决定。轻量用户装官方插件就能用，高级用户可以接外部引擎或者自己写插件。

---

## 3. 架构设计：谁管什么

动手之前先把职责划清楚。这是整个迁移中最重要的一步——后面所有的接口定义、数据流、前端改动都是从职责划分推导出来的。

### 3.1 三方职责

| 组件 | 职责 |
|------|------|
| **LangBot Core（宿主）** | 资源管理：LLM 模型、Embedding 模型、向量数据库连接、文件存储。RPC 服务端：响应插件发起的基础设施请求。流程驱动：协调文档入库和检索的任务分发。 |
| **Knowledge Engine 插件** | 业务策略：文档解析、文本分块、索引构建、查询改写、结果重排。通过 RPC 回调宿主获取基础设施支持（因为插件不直接持有向量库和模型句柄）。 |
| **Parser 插件**（远期规划） | 文件解析：接收特定格式的文件流，输出标准化内容对象。向宿主注册自己支持的文件类型。 |

关键决策是：**插件只做 DML（数据操作），不做 DDL（结构管理）。** 向量库的连接、Collection 创建由 LangBot 管理，插件只能在分配给它的 Collection 里做 Insert/Search/Delete。这样可以避免插件之间互相干扰，也简化了权限模型。

### 3.2 能力声明机制

不同的 RAG 引擎能力不同。一个对接外部 Dify 的插件只有检索能力（用户在 Dify 那边上传文档），而 LangRAG 这样的本地引擎既能入库又能检索。前端需要根据引擎的能力动态调整 UI。

我们用 **Capability 声明** 来解决这个问题：

```python
class KnowledgeEngineCapability:
    DOC_INGESTION = "doc_ingestion"    # 支持文档上传
    DOC_PARSING = "doc_parsing"        # 支持独立的文档解析
```

引擎在注册时声明自己的能力列表，前端据此决定是否渲染文档上传入口。这比用 `if type == "internal"` 做硬编码判断灵活得多——未来加新能力只需要加一个枚举值，不用改判断逻辑。

一开始我设计了四个能力（`DOC_INGESTION`、`CHUNKING_CONFIG`、`RERANK`、`HYBRID_SEARCH`），后来发现后三个没有实际消费者——分块配置、重排、混合检索这些行为完全可以通过插件自己的 `creation_schema` / `retrieval_schema` 来控制，不需要在宿主侧枚举。**只保留了 `DOC_INGESTION` 和 `DOC_PARSING`，因为这两个确实影响宿主决策（是否展示上传 UI、是否调度 Parser）。** 这是一次"设计过度 → 回收"的过程，说明能力枚举应该只包含影响宿主行为的项，纯插件内部的配置不需要上升到能力层面。

### 3.3 数据流

下面这张架构图是迁移前画的设计稿，描述了文档入库和检索两条链路中宿主与插件的交互边界：

![LangBot RAG 插件架构](/images/langbot-rag.png)

图中的关键分层：

- **实线框**（蓝色）是 LangBot 宿主提供的能力：解析器、嵌入模型、LLM、向量数据库、结构化数据库
- **虚线框**（橙色）是 RAG 引擎插件负责的业务逻辑：解析、分段、向量化调度、存储调度、问题解析、检索策略

**入库流程：**

```
用户上传文件
  → LangBot 保存到对象存储，生成 FileObject
  → 调用插件 ingest(file)
  → 插件内部：读取文件流 → 解析 → 分块 → 调 RPC 向量化 → 调 RPC 存储
  → 返回结果（成功/失败、Chunk 数量）
  → LangBot 更新文件状态
```

**检索流程：**

```
用户发起对话
  → LangBot 确定关联的知识库，调用插件 retrieve(query)
  → 插件内部：查询改写（可选）→ 调 RPC 向量化 → 调 RPC 搜索 → 重排（可选）
  → 返回 RetrievalResults
  → LangBot 拼接到 Prompt 提交给 LLM
```

两条链路的共同特征是：**插件驱动业务流程，宿主提供原子能力。** 插件决定"怎么分块"、"怎么检索"，但"用哪个模型 embed"、"往哪个向量库写"由宿主管。

---

## 4. RPC 接口：宿主暴露了什么

插件和宿主之间通过 Action 机制通信。我在 `RuntimeConnectionHandler` 中新增了以下 RPC Action：

| Action | 方向 | 用途 |
|--------|------|------|
| `INVOKE_EMBEDDING` | 插件 → 宿主 | 调用宿主配置的 Embedding 模型，返回向量 |
| `VECTOR_UPSERT` | 插件 → 宿主 | 向指定 Collection 写入向量和元数据 |
| `VECTOR_SEARCH` | 插件 → 宿主 | 在指定 Collection 中做向量/全文/混合检索 |
| `VECTOR_DELETE` | 插件 → 宿主 | 按元数据过滤条件删除向量 |
| `GET_FILE_STREAM` | 插件 → 宿主 | 获取宿主管理的原始文件内容 |
| `INVOKE_PARSER` | 插件 → 宿主 | 调用宿主侧注册的 Parser 插件 |

这套 RPC 由 `RAGRuntimeService` 统一承接：

```python
class RAGRuntimeService:
    """宿主侧的 RAG 基础设施服务，响应插件的 RPC 请求"""

    async def invoke_embedding(self, texts, model_uuid) -> list[list[float]]
    async def vector_upsert(self, collection_id, ids, vectors, metadata, documents)
    async def vector_search(self, collection_id, vector, top_k, filters, search_type, query_text)
    async def vector_delete(self, collection_id, filters)
    async def get_file_stream(self, file_key) -> bytes
```

### 文件传输的坑

一开始文件传输用的 base64 编码——把文件内容编码成字符串塞进 Action 的 payload 里。小文件没问题，但遇到几十 MB 的 PDF 就炸了：base64 编码会把体积膨胀 33%，加上 JSON 序列化的开销，一个 30MB 的文件在传输层变成了 40MB+ 的字符串，直接 OOM。

改成了 **chunked file transfer**：宿主通过 `send_file()` 把文件写到临时路径，返回一个 `file_key`，插件用 `read_local_file(file_key)` 按需读取。传输层只传一个路径字符串，实际的文件 I/O 在本地完成。这个方案在插件和宿主同机部署的场景下是零拷贝的。

---

## 5. 向量数据库的能力抽象

LangBot 支持多种向量数据库（Chroma、Qdrant、Milvus、pgvector、SeekDB），它们的能力差异很大。比如 Qdrant 支持混合检索（稀疏+稠密），而 Chroma 只支持纯向量检索。RAG 插件需要知道当前配置的向量库支持什么，才能选择最优策略。

为此我给 `VectorDatabase` 基类加了能力声明接口：

| 向量数据库 | 支持的能力 |
|-----------|-----------|
| Chroma | `metadata_filtering` |
| Qdrant | `hybrid_search`, `metadata_filtering`, `full_text_search` |
| Milvus | `hybrid_search`, `metadata_filtering`, `multi_tenancy` |
| pgvector | `metadata_filtering`, `full_text_search`（通过 PostgreSQL TSVector） |

同时统一了元数据过滤的语法。之前每个 VDB 实现的 filter 格式不一样（Qdrant 用 `models.Filter`，Milvus 用表达式字符串，pgvector 用 SQLAlchemy 条件），我写了一个 `filter_utils.py` 做统一翻译：插件侧统一用 Chroma 风格的 `{"file_id": "doc123"}` 语法，`filter_utils` 负责翻译成各后端的原生格式。

---

## 6. 数据模型统一

这次迁移最大的"破坏性变更"是 **砍掉了内置/外置知识库的区分**。

### 之前

```
KnowledgeBase（内置）          ExternalKnowledgeBase（外置）
├── embedding_model_uuid       ├── api_base_url
├── top_k                      ├── api_key
├── type = "internal"          ├── dataset_id
└── 内置解析/分块/检索          └── 转发到外部平台
```

两张表，两套 API，两套前端组件。

### 之后

```
KnowledgeBase（统一）
├── knowledge_engine_plugin_id    # 由哪个插件管理
├── collection_id                 # 向量 Collection 标识
├── creation_settings (JSON)      # 创建时的配置，不可变
├── retrieval_settings (JSON)     # 检索时的配置，可变
└── 所有操作转发给对应插件
```

一张表，一套 API。引擎之间的差异通过 `creation_settings` 和 `retrieval_settings` 这两个 JSON 字段来承载，具体的字段定义由插件通过 JSON Schema 声明，前端动态渲染表单。

**配置的可变性是一个有意的设计决策**：`creation_settings`（分块策略、索引模式、Embedding 模型）在创建后不可修改，因为改了就意味着已有的向量和新向量的语义空间不一致；`retrieval_settings`（top_k、相似度阈值、是否开启重排）随时可调，因为它们只影响查询行为。

数据库迁移脚本（`dbm020`）处理了存量数据的迁移：把旧的 `top_k` 字段搬到 `retrieval_settings` JSON 里，把 `embedding_model_uuid` 搬到 `creation_settings` 里，然后删掉 `external_knowledge_bases` 表。

---

## 7. LangRAG：官方 RAG 引擎插件

架构搭好之后，需要一个"跑起来"的引擎来验证。这就是 [LangRAG](https://github.com/langbot-app/langbot-plugin-demo/tree/main/LangRAG)——官方首选的 RAG 插件，作为 LangBot 的默认 RAG 实现。

### 7.1 三种索引策略

这是 LangRAG 相比旧内置实现最大的改进——支持多种索引策略，用户在创建知识库时选择：

**Chunk（平铺分块）**

最基础的策略。文档 → 递归切分 → 每个 Chunk 独立 embed → 存入向量库。适合通用场景。

```
文档 → [Chunk1, Chunk2, Chunk3, ...] → 各自 embed → 存储
检索：query embed → 向量搜索 → 返回 Top-K Chunks
```

**Parent-Child（父子分块）**

借鉴了 RAGFlow 等系统的分层索引思路。大块（Parent，默认 2048 字符）用于保留上下文，小块（Child，默认 256 字符）用于精确匹配。**检索时用 Child 的向量做相似度计算，但返回的是对应 Parent 的完整内容**，兼顾了检索精度和上下文完整性。

```
文档 → [Parent1, Parent2, ...] → 每个 Parent 切为 [Child1, Child2, ...]
                                    ↓
                               Child embed → 存储（metadata 记录 parent_index）
检索：query embed → 搜 Child → 按 parent_index 去重 → 返回 Parent 内容
```

一个实现细节：同一个 Parent 下的多个 Child 可能都命中，但我们只需要返回一次 Parent。LangRAG 的做法是 **over-fetch 3 倍**（取 `top_k * 3` 个 Child），然后按 `parent_index` 去重，保留每个 Parent 中得分最高的 Child。

**QA（问答对索引）**

入库时用 LLM 为每个 Chunk 生成问答对，**嵌入的是 Question 而不是原文**。检索时用户的 query 和 Question 做相似度匹配，命中后返回对应的 Answer。

```
文档 → [Chunk1, Chunk2, ...] → LLM 生成 [(Q1,A1), (Q2,A2), ...]
                                    ↓
                               Question embed → 存储（metadata 存 answer）
检索：query embed → 搜 Question → 返回 Answer
```

这个策略适合 FAQ 场景。代价是入库时需要额外的 LLM 调用，速度慢、成本高，但检索质量在问答场景下会好很多——因为用户的提问方式和 LLM 生成的问题在语义空间里天然更接近。

### 7.2 查询改写

LangRAG 还实现了三种查询改写策略，在检索前对用户的 query 做增强：

| 策略 | 原理 | 适用场景 |
|------|------|---------|
| **HyDE** | 让 LLM 生成一个"假想的理想文档"，用它的向量去搜索 | 用户 query 很短或很口语化时 |
| **Multi-Query** | 让 LLM 把一个 query 改写成 3 个不同表述，分别搜索后合并去重 | 提高召回率 |
| **Step-Back** | 让 LLM 生成一个更抽象的上位问题，用原始 query + 上位 query 同时搜索 | 复杂或多层次的问题 |

这三个策略都是可选的，用户在检索配置里选择是否开启。

### 7.3 文档解析与分块

RAG 系统里，解析和分块是容易被忽视但影响很大的环节。

**解析（Parser）** 的难点在于格式多样性。LangRAG 内置了轻量级解析器，支持 TXT、PDF、DOCX、Markdown、HTML 五种格式。但 PDF 解析是个老大难问题——PyPDF2 只能提取纯文本，碰到表格、多栏排版、扫描件就无能为力。我们在和 RAGFlow 做[技术对比分析](https://github.com/langbot-app/langbot-plugin-demo/issues/27)时，明确了一个策略：**RAGFlow 用 ONNX 模型解决的问题（布局分析、OCR），LangRAG 用 PyMuPDF 结构提取 + 视觉 LLM 来替代，保持轻量。** 后续会把 PDF 解析从 PyPDF2 升级到 PyMuPDF，覆盖 80% 的场景。

长期规划是把解析器做成独立的 **Parser 插件**（SDK 里已经定义好了 `Parser` 组件接口），这样用户可以针对特定的难解析格式（如扫描版 PDF）使用专用的 OCR 解析器，而不影响 RAG 索引逻辑。

**分块（Chunker）** 的核心权衡是粒度：太粗丢失检索精度，太细丢失语义上下文。LangRAG 的分块器用递归字符切分，分隔符按优先级递降：

```
段落（\n\n）→ 行（\n）→ 句号/问号/感叹号 → 逗号 → 空格 → 字符
```

支持中英日三种语言的标点。当前按字符数度量，后续计划改成按 token 数度量（参考 RAGFlow 的 `chunk_token_num`），用 tiktoken 或轻量估算函数实现，这样对 LLM 上下文窗口的预算更准确。

另一个值得做的改进是**标题感知的结构化分段**。RAGFlow 的 `hierarchical_merge` 能识别中英文标题和编号模式，在标题边界处切分而不是粗暴地按字符数切。这个用正则就能实现，零新依赖，LangRAG 的 GeneralParsers 已经返回了 `sections(heading, level, content)` 结构，只需要在分块时利用起来。

---

## 8. RAGFlow Connector：对接外部引擎的范例

为了验证插件架构的通用性，我们同时做了一个 [RAGFlowConnector](https://github.com/langbot-app/langbot-plugin-demo/tree/main/RAGFlowConnector) 插件，用来对接外部的 RAGFlow 服务。

它和 LangRAG 走的是完全不同的路径：

| 维度 | LangRAG | RAGFlowConnector |
|------|---------|-------------------|
| 解析/分块 | 插件内部实现 | 委托给 RAGFlow |
| Embedding | 通过 RPC 用宿主的模型 | RAGFlow 自己的模型 |
| 向量库 | 宿主管理的 VDB | RAGFlow 自己的 VDB |
| 高级功能 | HyDE、Multi-Query、Step-Back | GraphRAG、RAPTOR、Reranking |
| 部署要求 | 零额外依赖 | 需要独立部署 RAGFlow |

RAGFlowConnector 本质上是一个 HTTP API Wrapper——它把 `ingest()` 和 `retrieve()` 翻译成 RAGFlow 的 REST API 调用。但从 LangBot 的视角看，它和 LangRAG 是完全对等的 Knowledge Engine 插件，前端交互、知识库管理流程完全一致。

这正是插件化的价值：**用户不需要知道背后是 LangRAG 还是 RAGFlow，他们看到的是统一的"知识库"概念和统一的操作界面。** 引擎之间的差异通过动态表单消化掉了。

RAGFlowConnector 也验证了一件事：**对接外部 RAG 平台，写一个插件就够了，不需要在 LangBot 核心代码里加 if-else。** 未来对接 Dify Datasets、FastGPT 也是同样的模式。

---

## 9. 前端：从 Tab 切换到动态表单

前端的改动量不小（删了 ExternalKBCard、ExternalKBForm、ExternalKBRetrieve 等一堆组件），但核心思路很简单：

**之前**：内置知识库和外置知识库用 Tab 切换，两套独立的表单和卡片组件。

**之后**：统一的知识库列表，创建时选择引擎（从已安装的 Knowledge Engine 插件中选），表单根据插件返回的 `creation_schema` / `retrieval_schema`（JSON Schema）动态渲染。

动态表单还支持条件显示（`show_if`）。比如 LangRAG 的配置里，`parent_chunk_size` 和 `child_chunk_size` 只在选择了 `parent_child` 索引模式时才出现；`qa_llm_model_uuid` 只在选择了 `qa` 索引模式时才出现。这些条件由插件的 YAML Schema 定义，前端通用组件 `DynamicFormComponent` 负责解析和渲染。

---

## 10. 迁移过程中的几个决策

### Schema 声明从代码搬到 YAML

一开始创建/检索的配置 Schema 是通过 Python 方法返回的（`get_creation_settings_schema()` 返回一个 dict）。后来发现这样不好——Schema 是静态的声明式数据，放在代码里和运行时逻辑混在一起不清晰。最终改成了在插件的组件 YAML 文件里用 `spec.creation_schema` / `spec.retrieval_schema` 声明，SDK 加载时自动解析。

### 去掉了 RAGPluginAdapter 中间层

最初的设计有一个 `RAGPluginAdapter` 类，夹在 `RuntimeKnowledgeBase` 和 `plugin_connector` 之间做协议转换。实际写下来发现这层几乎没有业务逻辑——就是透传参数、格式转换。多一层抽象反而增加了调试难度（出了问题不知道该看 RuntimeKnowledgeBase 还是 Adapter 的日志）。果断删掉，让 RuntimeKnowledgeBase 直接调 plugin_connector。

**架构设计中"加一层"是本能反应，但每一层都要有存在的理由。** 如果一个中间层只做透传，它就不该存在。

### 知识库查找从列表改成字典

顺手修了一个性能问题：原来 `RAGManager` 里的知识库集合是 `list`，按 UUID 查找是 O(n) 遍历。改成了 `dict[str, KnowledgeBaseInterface]`，O(1) 查找。知识库数量不大时这个优化感知不到，但它消除了一个随着知识库数量增长而线性劣化的隐患。

---

## 11. 改动规模

最后量化一下这次迁移的工作量：

**LangBot 核心侧**（[PR #1995](https://github.com/langbot-app/LangBot/pull/1995)）：

- 涉及 **67 个文件**，+2959 / -1713 行
- 后端：RAGRuntimeService、RuntimeConnectionHandler、知识库模型统一、5 个向量数据库的 filter 适配、数据库迁移
- 前端：删除内置/外置 Tab 分栏、统一知识库列表、动态表单组件、多语言适配（中/英/日/繁体）

**Plugin SDK 侧**（[PR #34](https://github.com/langbot-app/langbot-plugin-sdk/pull/34)）：

- 涉及 **31 个文件**，+1781 / -643 行
- 新增 KnowledgeEngine 组件基类、RAG RPC 代理方法、Parser 组件接口、CLI 模板生成
- 删除旧的 KnowledgeRetriever、PolymorphicComponent

**插件侧**：

- LangRAG：3 种索引策略 + 3 种查询改写 + 5 种文件格式解析
- RAGFlowConnector：RAGFlow REST API 全量对接（含 GraphRAG/RAPTOR）
- DifyDatasetsConnector / FastGPTConnector：同模式的外部引擎对接

---

## 12. 前沿 RAG 技术与未来方向

架构迁移完成后，插件化的好处是：**试验新技术的成本变低了。** 不用改核心代码，写个新插件或者在 LangRAG 里加个策略就行。以下是我们在[技术对比分析](https://github.com/langbot-app/langbot-plugin-demo/issues/27)中评估过的几个前沿方向：

### 12.1 PageIndex：用文档结构导航替代纯向量搜索

VectifyAI 的 PageIndex 项目提出了一个有意思的思路：不做向量检索，而是用 LLM 推理遍历文档的目录树来定位相关内容。类似于人翻书——先看目录，判断哪个章节可能有答案，再翻到那一章细看。

完整实现太重了（每次查询都要多轮 LLM 推理，100 页文档构建索引需要 5-15 分钟），但它"结构感知"的思路值得借鉴。LangRAG 的 GeneralParsers 已经能返回文档的章节结构（heading + level + content），我们计划做一个轻量版的 **TOC 辅助检索**：入库时额外存储目录元数据（heading → chunk_id 映射），检索时可选让 LLM 先判断问题跟哪个章节相关，再结合向量搜索结果。作为可选策略，关掉就是纯向量检索，不增加默认开销。

### 12.2 RAPTOR：递归摘要树

RAPTOR（Recursive Abstractive Processing for Tree-Organized Retrieval）的思路是：对文档的 Chunk 做递归聚类，每层用 LLM 生成摘要，构建一棵从叶子（原始 Chunk）到根（全局摘要）的树。检索时可以在不同粒度上匹配——细节问题匹配叶子节点，全局性问题匹配上层摘要。

这个方案很优雅，但成本不低：多层递归 LLM 调用，需要 UMAP + GMM 聚类，构建时间长。LangRAG 已有的 QA 策略（LLM 生成问答对）在一定程度上覆盖了类似需求——QA 对本质上也是一种"用 LLM 预处理文档以提升检索质量"的思路，只是粒度和方式不同。短期内不引入 RAPTOR，但保持关注。

### 12.3 GraphRAG：知识图谱增强检索

微软 2024 年的 GraphRAG 论文提出用 LLM 从文档中提取实体和关系，构建知识图谱，支持多跳推理。RAGFlow 已经集成了完整的 GraphRAG 实现。

对 LangBot 来说，这个方向的判断是：**场景暂时不需要。** LangBot 主要是 IM 机器人场景，用户的问题通常是单跳的（"这个产品保修多久？"），很少需要多跳推理（"A 公司的 CEO 和 B 公司的 CTO 是什么关系？"）。加上 GraphRAG 的依赖很重（NetworkX、graspologic、图存储），与 LangRAG"轻量插件"的定位矛盾。不过通过 RAGFlowConnector 插件，用户已经可以直接使用 RAGFlow 的 GraphRAG 能力。

### 12.4 用 RAG 实现长期记忆

这是我个人最感兴趣的方向。当前 LLM 的对话记忆局限在上下文窗口内——窗口满了就得截断，之前的对话内容就丢了。RAG 天然适合解决这个问题：**把对话历史当作"文档"来索引，每轮对话结束后把关键信息 chunk 化、向量化存入知识库，下次对话时自动检索相关的历史上下文。**

具体的设想是：

1. **对话摘要入库**：每次对话结束后，用 LLM 提取关键信息（用户偏好、讨论过的话题、达成的共识），生成结构化摘要，存入专属的"记忆知识库"
2. **检索时融合记忆**：新对话开始时，除了检索业务知识库，还检索记忆知识库，把相关的历史上下文一并注入 Prompt
3. **记忆衰减**：给记忆条目加上时间权重，近期记忆权重高，久远记忆逐渐淡化（但不删除，仍可通过高相关度检索到）

这本质上是在用 RAG 实现一个外挂的"长期记忆系统"。有了插件化架构之后，这可以作为一个独立的 Knowledge Engine 插件来实现，不需要侵入 LangBot 核心逻辑。

### 12.5 技术选型的核心策略

我们在评估这些前沿技术时遵循的原则是：

| RAGFlow 方式 | LangRAG 替代方式 |
|-------------|-----------------|
| ONNX 布局分析模型 | PyMuPDF 结构提取 + 标题正则 |
| OCR 管线 | 视觉 LLM（invoke_llm 传图片） |
| 专用 Rerank 模型 | LLM Rerank（invoke_llm 打分） |
| IDF + 同义词词典 | 查询改写（HyDE / Multi-Query） |
| GraphRAG 知识图谱 | 通过 RAGFlowConnector 对接 |
| RAPTOR 摘要树 | QA 索引策略（已有） |
| PageIndex 树遍历 | TOC 辅助检索（轻量版） |

**用 20% 的复杂度覆盖 80% 的效果，保持插件的轻量和易部署。** 重量级能力通过对接外部引擎来补齐，而不是全部自己实现。

---

## 总结

这次迁移的核心不是"换了一种 RAG 实现"，而是**把 RAG 从固定功能变成了可插拔的能力。**

回头看，最关键的设计决策有三个：

1. **职责划分**：宿主管基础设施，插件管业务策略。边界清晰后，接口定义自然就出来了。
2. **统一数据模型**：砍掉内置/外置的区分，用 Capability + 动态 Schema 消化引擎差异。这比维护两套模型的成本低得多。
3. **能力枚举要克制**：只枚举影响宿主行为的能力，插件内部的配置用 Schema 自描述。过度枚举会让宿主和插件产生不必要的耦合。

架构迁移只是起点。有了插件化的基座，后续的 Parser 解耦、TOC 辅助检索、长期记忆系统都可以作为独立插件渐进地加入，每一步都不需要动核心代码。这大概就是"好架构"的意义——**不是一次性把所有事情做对，而是让未来做对的成本尽可能低。**

---

*本文涉及的代码变更：[LangBot PR #1995](https://github.com/langbot-app/LangBot/pull/1995)、[Plugin SDK PR #34](https://github.com/langbot-app/langbot-plugin-sdk/pull/34)、[LangRAG 插件](https://github.com/langbot-app/langbot-plugin-demo/tree/main/LangRAG)、[RAGFlowConnector 插件](https://github.com/langbot-app/langbot-plugin-demo/tree/main/RAGFlowConnector)、[技术对比分析](https://github.com/langbot-app/langbot-plugin-demo/issues/27)*
