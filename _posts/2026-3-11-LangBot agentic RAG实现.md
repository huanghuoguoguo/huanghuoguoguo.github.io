---
layout: post
title: "LangBot: 让 Agent 自己决定查不查知识库"
date: 2026-03-11
categories: [AI, 开源]
tags: [LangBot, RAG, Agent, Tool Calling, 插件架构]
comments: true
author: huanghuoguoguo
---

前两篇文章做了两件事：[RAG 架构迁移](/posts/LangBot-RAG迁移总结/)把知识库检索做成了插件化引擎，[长期记忆](/posts/LangBot-长期记忆设计/)把会话历史当 RAG 来做。但回过头看，两者有一个共同的问题——**检索时机不是 Agent 自己决定的**。

LangBot 当前的 `LocalAgentRunner` 做的是前置检索：用户消息进来，先无条件查一遍所有绑定的知识库，把结果拼进 prompt，然后才进入 Agent 的 tool loop。这就是所谓的 Naive RAG。

```
用户输入 → [强制 RAG 检索] → 结果拼入 prompt → Agent 执行（tool loop）
```

这个模式能用——而且有它自己的好处：简单、可预测，保证检索一定会发生，不存在该查却没查的情况。对于"用户大部分消息都跟知识库相关"的场景（比如内部客服系统），前置检索其实挺合适。

但 LangBot 不只是客服系统。它跑在微信群、QQ 群、飞书这些 IM 渠道上，大量消息是闲聊、打招呼、表情包——这些消息根本不需要知识库。

<!-- more -->

---

## Naive RAG 还可以更好

举个实际场景。用户在群里说"今天天气真好"，bot 绑定了三个知识库（产品手册、薪酬制度、考勤规则），Naive 模式下照样跑三次检索——拿"今天天气真好"去产品手册里搜向量相似的内容，结果当然是垃圾。浪费了三次 Embedding + 三次向量查询，召回的内容塞进 prompt 还占 token，甚至可能误导 LLM。

这不是边界情况，IM 场景下这是常态。

Naive 模式的局限在于检索逻辑太刚性：

| 局限 | 说明 |
|------|------|
| 无条件检索 | 不管用户问什么都触发，闲聊也查 |
| 单次检索 | 只查一次，结果不好也没有重试机会 |
| Agent 无控制权 | Agent 不能决定何时查、查什么 |
| Query 固定 | 用户原文直接当 query，不能改写或拆分 |
| 无法与其他 Tool 协同 | 检索和工具调用是分离的两个阶段 |

问题不是 Naive RAG 不能用，而是 **Agent 明明有判断能力，我们却没给它判断的机会**。一个有 tool calling 能力的 Agent 完全可以自己判断"这个问题需不需要查资料"，自己决定"去哪个库查、用什么 query 查"，甚至在第一次查的结果不够好时换个 query 再查一次。

这就是 Agentic RAG 的思路——把知识库检索变成 Agent 的一个 Tool，让 Agent 在 tool loop 里自主调用。

```
用户输入 → Agent 执行
              ├─ "需要查知识库" → 调用 RAG tool → 拿到结果
              ├─ "结果不够好" → 换 query 再调一次
              ├─ "需要补充信息" → 调 web search tool
              └─ "信息够了" → 生成回答
```

从"先查再答"变成"边想边查"。

---

## 行业里的 Agentic RAG 怎么做

Agentic RAG 的思路清楚了，但具体怎么落地？不同框架和团队的做法差别不小，大方向上有两种路线。

**路线一：RAG 框架自己做 Agent。** RAGFlow、Dify 这类平台在框架内部加了 Agent 编排能力——多轮检索、查询改写、结果校验都在框架里闭环完成。用户在 UI 上拖拽配置就能用，不需要自己写 Agent 逻辑。好处是开箱即用，坏处是 Agent 的决策逻辑被框架锁死，想接其他工具（网页搜索、数据库查询、外部 API）就得看框架支不支持。本质上是把 Agent 能力下沉到了 RAG 系统内部。

**路线二：上层 Agent 调用 RAG 作为工具。** 这是目前更主流的做法。RAG 系统退化成一个纯检索服务——接收 query，返回 chunks，不管生成。检索时机、query 构造、多轮策略、结果整合全部由上层 Agent 控制。LangChain、LlamaIndex 的 Agentic RAG 示例基本都是这个路线。

```
┌─────────────────────────────────┐
│  应用层：Agent 编排               │  ← 决策、规划、工具调用
├─────────────────────────────────┤
│  服务层：RAG 检索（纯 Retriever） │  ← 给 query，返 chunks
├─────────────────────────────────┤
│  基础设施：向量数据库、LLM API    │  ← 存储与计算
└─────────────────────────────────┘
```

| 维度 | 路线一：框架内置 Agent | 路线二：上层 Agent 调用 RAG |
|------|----------------------|---------------------------|
| 控制权 | RAG 框架主导，Agent 是框架内的流程组件 | Agent 主导，RAG 是工具之一 |
| 扩展性 | 受限于框架提供的工具集 | 可自由组合任意工具 |
| 适用场景 | 标准问答、快速搭建 | 复杂多步推理、多数据源协同 |

这里有个容易混淆的点：RAG 全称是 Retrieval-Augmented **Generation**，按字面意思"生成"也是 RAG 的职责。但在 Agentic 架构下，如果 RAG 服务把生成也做了——输入 query，直接输出最终答案——Agent 就失去了对生成过程的控制。它没法把检索结果和其他工具的结果组合起来回答，没法在第一次检索不够好时自己决定换 query 再查，也没法干预 prompt 的组装逻辑。

所以 Agentic RAG 里的"RAG"，实际干的是 **R** 的活——纯粹的信息获取。名字叫 RAG，角色是 Retriever。**G** 交给 Agent 统一控制。

LangBot 走的是路线二。RAG 引擎（LangRAG、Dify Connector、RAGFlow Connector）只提供检索能力，接口就是 `retrieve(query) → List[Chunk]`，从来不包含生成——这个分工在 [RAG 迁移](/posts/LangBot-RAG迁移总结/)时就定下了。现在要做的是：怎么把这个检索能力包装成 Agent 可以自主调用的 Tool，放进 LangBot 的插件体系里。

---

## 三个方案，两个被否

目标和路线都清楚了，问题在于具体怎么实现。这个 Tool 放在哪里、由谁提供，决定了整个方案的架构。

### 方案 A：在 KnowledgeEngine 插件里加 Tool

第一反应是给 LangRAG 这样的引擎插件直接加个 Tool 组件。引擎本来就管知识库的 ingest 和 retrieve，再加个 Tool 暴露给 Agent，看起来顺理成章。

实际想下去发现不对：

**职责混乱。** KnowledgeEngine 是数据层——入库、检索、删除。Tool 是应用层——面向 Agent 的交互接口。把两层混在一起，引擎插件的职责就不清楚了。

**重复实现。** LangRAG 要写一个 Tool，DifyDatasetsConnector 也要写一个，RAGFlowConnector 还要再写一个。每个引擎插件都重复实现同样的"列出知识库、执行检索"逻辑。

**隔离丢失。** 这是最致命的问题。LangBot 的知识库是按 pipeline 隔离的——pipeline A 绑定了 KB1 和 KB2，pipeline B 绑定了 KB3。但 KnowledgeEngine 插件不感知 pipeline 配置，它只知道自己管的那些 KB。如果 Tool 在引擎插件里，它没办法做 pipeline 级别的访问控制——Agent 可能查到不该查的知识库。

**元数据在宿主侧。** 知识库的 name 和 description 存在 LangBot 核心的数据库里，不在引擎插件中。Tool 需要把 KB 的描述告诉 Agent，让它判断该查哪个库，但引擎插件拿不到这些信息。

否决。

### 方案 B：改 LocalAgentRunner

另一个思路是直接在 LangBot 核心的 `LocalAgentRunner` 里注入一个内置 RAG Tool。

问题很简单——不符合插件化理念。RAG 迁移那篇文章的核心结论就是：**业务逻辑不要写在核心代码里。** 内置 Tool 意味着用户不能选择是否启用 agentic 模式，也不能自定义 Tool 的行为。而且每次改 Tool 的逻辑都要发核心版本，社区贡献门槛高。

否决。

### 方案 D：独立插件 + SDK API 扩展

（没有方案 C，因为讨论过程中直接跳到了 D。）

最终的思路是拆成两层：

1. **LangBot 核心**：在 SDK 里加两个新的 API，让插件能查询 pipeline 级别的知识库列表和执行检索
2. **独立插件**：新建一个 `AgenticRAG` 插件，只包含一个 Tool 组件，通过新 API 完成所有操作

```
AgenticRAG Plugin (独立插件)
  │
  │ Tool 被 Agent 调用
  │
  ├─ action="list"
  │   → SDK API: list_pipeline_knowledge_bases(query_id)
  │   → LangBot 根据 query_id 找到 pipeline config
  │   → 返回该 pipeline 绑定的 KB 列表（uuid, name, description）
  │
  └─ action="query"
      → SDK API: retrieve_knowledge(query_id, kb_id, query_text)
      → LangBot 校验 kb_id 在 pipeline 允许范围内
      → 调用 RuntimeKnowledgeBase.retrieve()
      → 自动路由到对应引擎（LangRAG / Dify / RAGFlow）
      → 返回检索结果
```

这个方案的好处一目了然：

| 特性 | 说明 |
|------|------|
| Pipeline 隔离 | API 基于 query_id 查 pipeline config，只暴露该 pipeline 的 KB |
| 跨引擎 | RuntimeKnowledgeBase.retrieve() 自动路由到对应引擎插件 |
| KB 描述可用 | 直接从数据库读 name/description，Agent 能判断查哪个库 |
| 引擎插件不动 | LangRAG/DifyRAG/RAGFlow 等零改动 |
| 可选安装 | 不装此插件就是原有 naive 模式 |
| 改动量小 | SDK 加 2 个枚举 + 2 个方法，LangBot 加 2 个 handler |

关键在于 **"引擎插件不动"**。RAG 迁移时设计的 KnowledgeEngine 接口已经有 `retrieve()` 方法，AgenticRAG 只是换了一个调用时机——从 runner 前置调用变成 Agent tool loop 里按需调用。整个检索链路（引擎路由、向量搜索、结果格式化）完全复用，新插件只做"什么时候调、调哪个"的决策层。

这和长期记忆插件的思路是一致的：记忆插件复用了 KnowledgeEngine 的检索通道来注入记忆，AgenticRAG 复用同样的通道但把调用权交给了 Agent。RAG 迁移时搭的基础设施在这里又一次体现了价值。

---

## 实现细节

这个方案目前还在设计阶段，代码还没开始写。以下是确定下来的实现思路，改动分三块：SDK、核心、插件。

### SDK 侧：两个新 API

在 `QueryBasedAPIProxy` 里加两个方法，对应两个新的 RPC action：

```python
async def list_pipeline_knowledge_bases(self) -> list[dict]:
    """列出当前 pipeline 绑定的知识库"""
    # 基于 query_id 查找 pipeline config → 返回 KB 列表

async def retrieve_knowledge(self, kb_id: str, query_text: str, top_k: int = 5) -> list[dict]:
    """检索指定知识库"""
    # 校验 kb_id 在 pipeline 允许范围 → 调用 RuntimeKnowledgeBase.retrieve()
```

这两个 API 都是 **query-scoped** 的——继承自 `QueryBasedAPIProxy`，内部自动携带 `query_id`，由宿主侧根据 query_id 查找对应的 pipeline 配置。插件不需要也不能直接指定 pipeline，隔离在 API 层面就做好了。

### 核心侧：两个 handler

在 `RuntimeConnectionHandler` 里加两个 action handler（和 RAG 迁移时加 `INVOKE_EMBEDDING`、`VECTOR_UPSERT` 是同样的模式）：

**LIST_PIPELINE_KNOWLEDGE_BASES handler**：
```
query_id → 查 Query 对象 → 拿到 pipeline_config
→ 读 knowledge-bases UUID 列表
→ 从 rag_mgr 获取每个 KB 的 name, description
→ 返回 [{uuid, name, description}, ...]
```

**RETRIEVE_KNOWLEDGE handler**：
```
query_id + kb_id → 校验 kb_id 在 pipeline 的 KB 列表中
→ 调用 RuntimeKnowledgeBase.retrieve(query_text, top_k)
→ 返回检索结果
```

安全校验：如果 kb_id 不在当前 pipeline 的 knowledge-bases 列表中，直接返回错误。防止 Agent 被 prompt injection 诱导去查不该查的库。

### 插件侧：一个 Tool

AgenticRAG 插件只有一个 Tool 组件，目录结构很简单：

```
AgenticRAG/
├── manifest.yaml
├── main.py
└── components/tools/
    ├── query_knowledge.yaml    # Tool 定义
    └── query_knowledge.py      # Tool 实现
```

Tool 定义里声明两个 action：`list`（列出可用 KB）和 `query`（检索指定 KB）。实现里就两个分支，分别调 SDK 的对应方法，全部逻辑加起来不超过 50 行。

---

## API 交互示例

用一个具体场景走一遍。

用户在 pipeline A（绑定了"薪酬管理"和"考勤制度"两个 KB）里问："年终奖怎么算？"

**Step 1**：Agent 判断需要查知识库，先调 Tool 列出可用 KB。

请求：
```json
{"action": "list"}
```

响应：
```json
{
  "knowledge_bases": [
    {"uuid": "kb-001", "name": "薪酬管理", "description": "公司薪酬制度、绩效考核、年终奖规则..."},
    {"uuid": "kb-002", "name": "考勤制度", "description": "出勤打卡规则、请假流程..."}
  ]
}
```

**Step 2**：Agent 看到 KB 描述，判断"年终奖"应该在"薪酬管理"里，构造 query 去查。

请求：
```json
{"action": "query", "kb_id": "kb-001", "query_text": "年终奖计算规则", "top_k": 5}
```

响应：
```json
{
  "results": [
    {"content": "年终奖按照员工当年度绩效考核结果...", "metadata": {"file": "薪酬手册.pdf", "page": 12}},
    {"content": "绩效等级对应的年终奖系数：S=3.0, A=2.0...", "metadata": {"file": "薪酬手册.pdf", "page": 13}}
  ]
}
```

**Step 3**：Agent 拿到结果，生成回答。如果结果不够好，可以换个 query 再查，或者去考勤制度库里补充查一下出勤天数对年终奖的影响。

整个过程中，Agent 自己决定了查哪个库、用什么 query。如果用户问的是"今天天气真好"，Agent 压根不会调这个 Tool——零检索开销。

---

## 和 Naive 模式的共存

一个设计原则是 **Agentic RAG 是增量能力，不破坏现有模式**。

不装 AgenticRAG 插件，LangBot 和之前一样——`LocalAgentRunner` 前置检索，pipeline 绑定的 KB 自动查。装了插件之后，pipeline 配置方式也不变，只是多了一个 Agent 可以主动调用的 Tool。

但有一个实际问题需要注意：如果同时开启了 naive 前置检索和 agentic 模式，同一个 KB 可能被查两次——前置检索查一次，Agent 的 Tool 再查一次。所以在使用 AgenticRAG 插件时，建议关闭前置 RAG 检索。后续计划在 pipeline 配置里加一个 `rag-mode` 开关：

```yaml
# pipeline config，二选一：
rag-mode: naive      # 前置检索（默认）
# rag-mode: agentic  # Agent 自主检索，关闭前置
```

切换一个字段就行，不需要改 KB 绑定。

---

## 需要注意的问题

Agentic RAG 不是银弹，有几个已知的坑需要跟进：

**漏检索。** 这是 Agentic 模式最需要警惕的问题。Naive 模式保证检索一定发生，Agentic 模式把"要不要查"交给了 Agent——Agent 可能判断失误。用户说"加班到几点算加班费？"这种口语化表述，Agent 有可能当成闲聊跳过检索，结果凭通用知识胡说一通。缓解思路有几个：在 system prompt 里给 Agent 明确的检索引导规则（"涉及公司制度的问题必须查知识库"），或者对特定关键词/场景设置强制检索的兜底逻辑。这是 Agentic RAG 相比 Naive 模式的核心 trade-off——用检索的灵活性换来了判断的不确定性。

**上下文膨胀。** Agent 在 tool loop 里可能多次调用 RAG Tool，每次返回的检索结果都会累积到上下文里。查三次、每次返回 5 条，就是 15 条文档片段塞在消息历史中。这和 [#2051](https://github.com/langbot-app/LangBot/issues/2051) 讨论的 Agent loop 上下文保护问题直接相关——需要有截断或摘要机制，防止上下文窗口被检索结果撑爆。

**并行调用。** 如果 Agent 想同时查两个 KB，理想情况下两个 Tool call 应该并行执行。这依赖 [#2050](https://github.com/langbot-app/LangBot/issues/2050) 里讨论的 Tool Calls 并行执行支持。当前 LangBot 的 tool loop 是串行的，多次检索会叠加延迟。

**成本可预测性。** Naive 模式的开销是确定的——每次固定查 N 个 KB。Agentic 模式下 Agent 可能不查（省了），也可能查很多次（贵了），开销波动大。好处是闲聊场景下省了大量无效检索，坏处是复杂问题可能触发比 Naive 更多的调用。需要观察实际使用中 Agent 的调用分布，必要时加 Tool 调用次数上限。

---

## 演进路线

分四步走：

1. **Phase 1（当前）**：SDK 加两个 API，新建 AgenticRAG 插件，跑通基础流程
2. **Phase 2**：LocalAgentRunner 加 `rag-mode` 配置，自动控制前置检索的开关
3. **Phase 3**：动态 Tool 描述——支持 Tool 的 prompt 模板化，注册时自动把 KB 的 name 和 description 注入 Tool 描述。这样 Agent 看到 Tool 就知道有哪些库可查，不需要先调 list 再调 query，省掉一轮 tool call。每轮 tool call 意味着一次完整的 LLM 推理，少一轮就是少一次推理的 token 和延迟
4. **Phase 4**：高级 Agentic RAG——跨库联合查询、Agent 自动 query rewrite、检索结果置信度评分与重试策略

Phase 1 的改动量很小：SDK 两个文件、核心一个文件、插件一个新 repo。

---

## 回头看这三篇文章

从 RAG 迁移到长期记忆再到 Agentic RAG，三篇文章其实在做同一件事：**把 LangBot 从一个"代码里写死了怎么用 LLM"的框架，变成一个"让 Agent 自己决定怎么用工具"的框架。**

RAG 迁移把检索策略的选择权从核心代码交给了引擎插件。长期记忆把"记什么"的决定权交给了 LLM 的 Tool calling。现在 Agentic RAG 把"查不查、查什么"的决定权也交给了 Agent。

方向是一致的：**越来越多的决策从硬编码逻辑移到了 Agent 的自主判断。** 框架的角色从"编排者"变成"基础设施提供者"——提供能力（检索、存储、嵌入），但不替 Agent 决定什么时候用、怎么用。

但这里有一个隐含的赌注：**我们在赌 Agent 的判断力够用。** 让 Agent 决定记什么，它可能记错；让 Agent 决定查不查，它可能漏查。每一次把控制权从确定性逻辑交给概率性模型，都是在用灵活性换不确定性。

当前阶段这个赌注成不成立，取决于具体场景。高风险场景（医疗、法务）可能还是 Naive 模式更稳妥——宁可多查几次垃圾，不能漏掉关键信息。低风险场景（闲聊群、兴趣社区）Agentic 模式明显更合适——没必要每句话都跑一遍知识库。

所以最终的答案可能不是二选一，而是让用户根据自己的场景选择。这也是为什么我们把 Agentic RAG 做成可选插件，而不是替换掉 Naive 模式——**框架不替用户做判断，就像我们不替 Agent 做判断一样。**

---

*本文是设计阶段的记录，实现后会补充代码链接。相关资源：[LangBot](https://github.com/langbot-app/LangBot)、[Issue #2050](https://github.com/langbot-app/LangBot/issues/2050)（Tool Calls 并行）、[Issue #2051](https://github.com/langbot-app/LangBot/issues/2051)（Agent 上下文保护）*
