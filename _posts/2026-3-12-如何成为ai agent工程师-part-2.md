---
title: "如何成为 AI Agent 工程师（二）：Harness Engineering 与系统化实践"
date: 2026-03-12
categories: [AI, 工程实践]
tags: [AI Agent, Harness Engineering, Context Engineering, Codex, 工程系统]
---

这是这个系列的第二部分。先说明一下：**这一篇的核心内容，主要整理自小红书作者 `ody` 对 `sysls` 那篇文章的转述，我基本保留了原意，只做了 Markdown 化、结构整理和少量表达顺序调整。**

和第一篇一样，这篇仍然以整理为主。文中的少量引用块，是我自己在实习和用 AI 写代码时，和这些材料慢慢对上的一些感受。

第一部分讲的是个人开发者如何把 agent 用好：从最小配置出发，通过上下文控制、rules 和 skills，把 agent 逐步训练成“按你的方式工作”的工程搭档。

这一篇往前再推一步，讨论的是另一个层级的问题：**当你不只是想“自己用顺手”，而是想让团队、系统、甚至组织规模的 agent 都稳定工作时，该怎么做？**

OpenAI 在 2026 年 2 月发布的 `Harness engineering: leveraging Codex in an agent-first world`，给了这件事一个正式的名字：**Harness Engineering**。

---

## 1. AI 大厂内部怎么用 Agent 写代码

OpenAI 在今年 2 月发了一篇内部实验报告。按文中披露，这个结论很直接：**3 个工程师，5 个月，用 Codex 写出了一个完整的测试版产品。**

一些关键数字非常夸张：

- 约 100 万行生产代码；
- 应用逻辑、测试、CI 配置、文档、内部工具，几乎全部由 agent 生成；
- 超过 1500 个 PR 被合并；
- 人均每天合并 3.5 个 PR；
- 团队后来扩到 7 人，吞吐量还在继续增长；
- 他们估算，这套方式的效率大约是纯手写的 10 倍。

但早期最大的问题，不是模型不行。

实验刚开始时，进展比预期慢很多。真正拖后腿的是环境规格不足：**agent 缺乏完成高层目标所需的工具、抽象和内部结构。**

你给它一个模糊目标，它不知道该去哪里找信息，不知道代码边界在哪里，也不知道什么叫“做完了”。

这和第一部分谈的“上下文控制”其实是一回事。只是到了系统层面，这件事有了一个更正式的名字：**Harness Engineering**。

## 2. Harness Engineering 到底是什么

一句话概括：

> 设计包裹在 agent 周围的基础设施、约束和反馈循环，让 agent 在规模化场景下可靠工作。

Martin Fowler 看完 OpenAI 那篇文章后的评价是：这是“AI 赋能软件开发的关键框架”。

很多人会把几个概念混在一起，其实可以这样理解：

- `Prompt Engineering` 管的是一次对话；
- `Context Engineering` 管的是上下文窗口里放什么信息；
- `Harness Engineering` 管的是整个系统生命周期，包括环境、约束、反馈和维护。

三者的范围是逐层扩大的。大多数人今天还停留在第一层。

## 3. 三根支柱

OpenAI 把自己的 harness 拆成了三个核心组件：**上下文工程、架构约束、熵管理**。

### 3.1 上下文工程

上下文又可以分成两类。

**静态上下文**

- 仓库文档；
- `AGENTS.md` / `CLAUDE.md`；
- 设计规格书。

**动态上下文**

- 可观测性数据；
- 目录映射；
- CI/CD 状态。

核心原则只有一条：

> agent 上下文里没有的东西，对它来说就不存在。

这和第一部分里“`CLAUDE.md` 应该是逻辑路由表”“计划和实现要分到不同会话里”完全一致。底层逻辑都一样：**精确控制 agent 能看到什么。**

OpenAI 只是把这种个人实践，上升成了工程规范。

例如，一个成熟仓库里可能会给 agent 准备这样一组入口文档：

```text
AGENTS.md
ARCHITECTURE.md
docs/design-docs/index.md
core-beliefs.md
exec-plans/active/
completed/tech-debt-tracker.md
generated/db-schema.md
product-specs/index.md
new-user-onboarding.md
references/design-system-reference-llms.txt
nixpacks-llms.txt
uv-llms.txt
```

### 3.2 架构约束

OpenAI 使用了严格的分层依赖，例如：

```text
Types / Config -> Repo -> Service -> Runtime -> UI
```

这些边界不是靠“大家自觉”维持，而是靠确定性的工具去执行：

- `linter`
- 结构测试
- `pre-commit hook`

Agent 写的每一行代码都必须通过这些检查。

一个看起来违反直觉、但非常重要的结论是：**约束越多，agent 往往越高效。** 因为解空间被收窄了，agent 不需要在无数种可能的实现方式里迷路。

回头看，第一部分提到的 `rules` 和 `skills`，本质上也是一种轻量级架构约束。你告诉 agent“遇到这种情况按这个方式做”，其实就是在收窄它的解空间。

> 我后来越来越认同这一点。约束看起来像是在卡人，真落到项目里，它很多时候是在替你挡住 AI 和自己一起失控。

原文里还给了一个更抽象的分层示意，可以概括成：

```text
Layered domain architecture with explicit cross-cutting boundaries

Utils
Business logic domain
Providers
Service
Types
App Wiring + UI
Runtime
Config
UI
Repo
```

### 3.3 熵管理

代码库会腐烂，文档会过时，命名会漂移。人写代码如此，agent 写代码更是如此，因为速度快太多了。

OpenAI 的做法是定期运行“清理 agent”：

- 检测文档和代码是否不一致；
- 查找死代码；
- 修复命名漂移；
- 按日频或周频执行。

这和第一部分提到的个人实践同样是一致的：当 rules 积累到一定程度时，要清理、合并、去冲突、删过时内容。

个人版叫整理规则，系统版叫**熵管理**。

所以这三根支柱，正好对应三个工程问题：

- agent 看到了什么：上下文；
- agent 能做什么：约束；
- 系统怎么避免腐烂：熵管理。

## 4. 只改 harness，不换模型

如果你还在想“等下一代模型出来就好了”，那有两个案例值得看。

**案例 1：LangChain 在 Terminal Bench 2.0 上的实验**

模型完全不动，只改 harness。具体包括：

- 自验证循环；
- 更好的上下文工程；
- 循环检测；
- 推理优化。

按 LangChain 公布的 Terminal Bench 2.0 结果，分数从 `52.8%` 跳到 `66.5%`，排名从第 30 名升到第 5 名。

**案例 2：Stripe 内部的 Minions 系统**

按 Stripe 对外分享，内部有一个叫 `Minions` 的系统，每周自动合并 `1000+` 个 PR。从任务描述、代码生成到最终合并，整个流程都由 agent 完成。

这两个案例共同说明了一件事：

> 在模型能力逐步接近的情况下，harness 越来越像真正的护城河。

同一个模型，在粗糙 harness 里表现平庸，在精心设计的 harness 里表现惊人。差距主要来自系统设计，而不是模型参数。

> 后来我做一个内部项目时，最难受的地方也不是模型不够强，而是它太忠实了。目标一旦还是糊的，它就会很快把这种模糊翻译成一大片实现，帮你把错误方向也一起做实。

## 5. 从个人到系统的升级路径

把第一部分和 Harness Engineering 放在一起看，会得到一条很清晰的升级路径。

**个人层面**

- `CLAUDE.md` 做路由表；
- 用 `rules` / `skills` 持续迭代；
- 把计划调研和实现分离到不同会话。

这是大多数个人开发者现在就应该做的事。

**团队层面**

- 用 `AGENTS.md` 统一规范；
- 把架构约束推进到 CI；
- 提供稳定的 prompt 模板；
- 建立文档验证流程。

这时候，你就需要 `linter` 和结构测试了。

**组织层面**

- 自定义中间件；
- 集成可观测性；
- 建性能仪表盘；
- 做自动熵管理。

这就是 OpenAI 和 Stripe 正在做的事。

大多数人卡住的位置，是从“个人好用”走向“团队都好用”。

跨过去的关键，是把隐性知识显性化。你脑子里那些“我一般会这么做”的经验，必须变成：

- linter 规则；
- CI 检查；
- 文档规范；
- 可执行约束。

只有能被机器执行的规则，才能在规模化场景下长期存活。

## 6. 工程师能力的迁移

工程师的核心能力，正在从“自己写代码”，迁移到“设计让 agent 写好代码的系统”。

半年前，我还在手动管理上下文；现在 `rules` 和 `skills` 已经替我自动化了大部分决策。再过半年，我大概会觉得今天这套做法也很粗糙。

这个迁移的速度，可能比大多数人预期得更快。而 `Harness Engineering` 这个框架，恰好给了它一个正式的名字，以及一套更系统的方法论。

## 7. 为什么我后来会越来越信这些

如果只看概念，`Harness Engineering` 很容易被理解成大公司才需要的重型做法。但我后来越来越觉得，它之所以重要，不是因为名字新，而是因为软件开发本来就比普通 agent 调用重得多。

问答和一次性任务，结果通常是当场消费掉的。代码不是。代码会留下来，会跟系统里别的代码继续发生交互，也会被后面的功能、测试、文档、CI 和其他人反复接手。模型越强，低层脚手架也许会变轻，但这些工程约束不会消失。

而且 AI 的代码产能越高，熵涨得往往越快。文档更容易过时，接口更容易漂移，风格更容易失真，无人真正理解的代码也更容易堆起来。到这个时候，`harness` 就不再只是“辅助模型发挥更好”，而是在替项目守住最起码的可维护性。

所以我现在再看前两篇，真正留下来的不是某个新名词，而是一个更朴素的判断：**要持续收束 AI 在工程问题上的解空间。** 上下文、约束、熵管理，看起来分属不同层次，落到项目里其实都在做同一件事。

所以最后的问题其实不是：

> 你会不会用 agent？

而是：

> 你现在的 harness，是什么样的？

下一篇我会回到自己的一个实习项目，写一个更具体的反例：当需求边界、测试契约和工程约束都不稳定时，AI 是怎么把问题更快放大的。

参考资料：

- OpenAI, `Harness engineering: leveraging Codex in an agent-first world`, 2026 年 2 月  
  https://openai.com/index/harness-engineering/
- Martin Fowler, `Harness Engineering`  
  https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html
- NxCode, `Harness Engineering: The Complete Guide`  
  https://www.nxcode.io/resources/news/harness-engineering-complete-guide-ai-agent-codex-2026
