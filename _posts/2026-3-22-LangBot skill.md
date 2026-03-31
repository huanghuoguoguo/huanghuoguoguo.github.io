---
layout: post
title: "给 LangBot 装上技能系统"
date: 2026-3-22
categories: [AI, 架构设计]
tags: [LangBot, Skills, Agent, 沙箱]
comments: true
author: huanghuoguoguo
---

[前一篇]({% post_url 2026-3-20-LangBot沙箱设计 %})讲了 LangBot Box 的沙箱设计——怎么让不可信代码跑在容器里。沙箱底座做完之后，一个很自然的问题就来了：agent 现在能安全地执行代码了，但它执行的代码从哪来？

`exec` 解决了"怎么安全地跑"的问题，但没有解决"跑什么"的问题。模型每次都要从零开始写脚本，写完跑一次就扔了。如果某个任务经常做——比如代码审查、日志分析、数据清洗——每次都让模型重新写一遍，既慢又不稳定。

所以我们给 LangBot 加了一套 skill 系统。

<!-- more -->

---

## 先说 skill 是什么

skill 是一个可复用的专业知识包，本质上就是文件系统里的一个目录。

```text
my-skill/
├── SKILL.md
├── scripts/
│   └── review.py
├── references/
│   └── runbook.md
└── assets/
    └── config.yaml
```

`SKILL.md` 是唯一必需的文件，告诉模型这个 skill 干什么、怎么用。`scripts/` 里放可执行脚本，`references/` 放参考资料，`assets/` 放模板和配置。

**skill 本身不是工具**。`scripts/` 里的脚本也不是独立工具。skill 告诉 agent"何时做什么、去哪里找资源、推荐执行什么命令"，但真正执行时仍然走统一的通用工具——`exec`、`read`、`write`、`edit`。

这和 skill 的 MVP 设计有很大不同。一开始我们想过让 skill 自带工具、独立注册、通过 `skill__{name}__{tool}` 的方式暴露给模型。后来觉得那样会把工具面打散，每个 skill 都造自己的执行抽象，agent 的心智负担太重。现在收敛成：skill 是"指令包 + 资源包"，执行能力统一走 `exec`。

---

## 文件系统是唯一真源

skill 以文件系统为唯一真源，不进入数据库。

默认技能目录是 `data/skills/{name}/`，包含：

```text
data/skills/
├── deploy-checker/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
└── log-analyzer/
    ├── SKILL.md
    └── ...
```

启动时扫描 `data/skills/`，从 `SKILL.md` 解析 `name`、`display_name`、`description`、`auto_activate`，把 metadata 加载到内存 catalog。真正触发 skill 时，再按需读取最新的 `SKILL.md`、scripts、references、assets。

这意味着：

- skill 不存数据库，不用 uuid
- API 和 pipeline 绑定统一按 `name` 工作
- skill 可以自然地被复制、git 管理、导入、导出、共享
- 没有"文件版 skill"和"数据库版 skill"双写漂移的问题

---

## 运行时工具面

skill 不再拥有专属的 runtime tool。

早期的设计里，skill 可以声明自己的工具，每个工具注册到模型的可用列表里，调用时通过 `skill__{skill_name}__{tool_name}` 的命名空间来区分。比如 `skill__code-review__run_review`。

现在的设计收敛了：skill 只负责说明"应该做什么"，实际执行统一用 LangBot 的通用工具。

运行时真正的工具组合：

- `exec` —— 执行命令
- `read` —— 读取文件
- `write` —— 写入文件
- `edit` —— 编辑文件

skill 激活后，它的资源目录以统一文件系统路径暴露给 agent，例如 `/workspace/.skills/<skill-name>/`。agent 用 `read` 探查 `SKILL.md`，用 `exec(workdir="/workspace/.skills/<skill-name>")` 执行脚本。

这样设计的好处：

- agent 心智更简单，只理解"加载 skill"与"执行通用工具"
- LangBot 框架可以统一处理 sandbox、tool policy、approval/elevated
- 避免"文件版 skill"和"数据库版 skill"双写漂移
- 和 OpenCode 的 `skill + bash/read/edit`、OpenClaw 的 `skills + exec/system.run` 更一致

---

## pipeline 绑定模型

skill 是否对某个 pipeline 生效，通过 pipeline 的 `extensions_preferences` 管理。

```json
{
  "enable_all_skills": true,
  "skills": ["deploy-checker", "log-analyzer"]
}
```

- `enable_all_skills=true`：该 pipeline 对所有已加载 skill 开放
- `enable_all_skills=false`：仅 `skills` 列表里的 skill 可用

这和 plugin / MCP 的 pipeline 扩展模型保持一致，不需要额外的 skill binding 表，不需要 skill uuid，不需要单独的 bind / unbind API。

---

## 在沙箱里跑

skill 的执行走 Box 沙箱，通过统一的 `exec` 工具完成。

skill 激活后，系统把 skill 的 package 目录以统一路径暴露到当前 agent 工作上下文，例如 `/workspace/.skills/<skill-name>/`。agent 继续用通用工具工作：

- `read(path="/workspace/.skills/<skill-name>/SKILL.md")` —— 查看 skill 说明
- `exec(command="python scripts/review.py", workdir="/workspace/.skills/<skill-name>")` —— 执行脚本

skill 的 `scripts/`、`references/`、`assets/` 都在这个路径下，agent 可以直接访问。

执行时的安全边界：

- package 目录挂载只读（当前实现），或 package 只读 + state 目录可写（目标方向）
- 默认 network 关闭，timeout 30 秒
- 资源限制、工作目录、网络策略由 Box profile 和 LangBot policy 统一控制

skill 不负责自己的安全边界，安全由 LangBot + Box 保证。

---

## 安全上的考虑

skill 的安全模型和 `exec` 有区别。`exec` 执行的是 LLM 生成的代码，完全不可信。skill 执行的是管理员预先放好的脚本，半可信——你至少知道脚本里写了什么。

但即便如此，该有的边界还是得有：

- skill package 的 `host_path` 要通过 allowlist 校验。不能随便传个 `/etc` 进来
- package 挂载强制只读。脚本不能修改自己
- 脚本路径必须是 package 内的相对路径，不允许 `..` 逃逸
- 安全边界最终靠 LangBot + Box：sandbox policy 决定默认在哪执行，tool policy 决定哪些工具可用，approval/elevated policy 决定某次 `exec` 是否可越过默认限制

skill 不单独定义安全边界，不依赖"只能执行预先注册命令"的白名单机制。

---

## 一个完整的流程

把整个链路串一遍：

1. 管理员创建一个 skill，在 `data/skills/my-skill/` 下放好 `SKILL.md` 和 `scripts/`
2. LangBot 启动时扫描 skill 目录，加载 skill index
3. 用户对话中，系统根据 pipeline 的 `extensions_preferences` 注入可见 skill index
4. agent 判断需要激活这个 skill，输出 `[ACTIVATE_SKILL: my-skill]`
5. 系统读取 `SKILL.md`，把内容追加到 prompt
6. 系统把 skill 的资源目录以统一路径暴露到当前 agent 工作上下文，例如 `/workspace/.skills/my-skill/`
7. 第二轮 LLM 请求里，模型看到了 skill 的完整 instructions 和资源路径
8. 模型决定执行脚本，调用 `exec(command="python scripts/review.py", workdir="/workspace/.skills/my-skill")`
9. Box Runtime 在沙箱内执行，返回 stdout/stderr/退出码
10. 结果回到模型，模型基于结果继续对话

关键点是：skill 激活后，agent 看到的不是新增了一堆专属工具，而是"我知道有个 skill 可以用了，它的资源在某某路径，我需要的时候可以用通用工具去操作"。

---

## 后面还想做的

当前设计已经收敛，但还有一些工程细节要补。

**多挂载点。** 现在 Box 只能把一个 `host_path` 挂到 `/workspace`。理想的情况是 package 挂到 `/skills/<name>`（只读），再给 skill 一个独立的 state 目录挂到 `/state/skills/<name>`（可写），用来存持久化状态。

**持久化状态。** 现在 skill 跑完一次，容器回收了，状态就没了。有些 skill 需要跨 session 保留一些东西——缓存、索引、上次的分析结果。需要独立的 `state_root` 加上配额和生命周期管理。

**自定义镜像和 profile。** 目前 skill 用的是默认镜像。有些 skill 可能需要特定的运行环境——比如需要 `ffmpeg` 或者某个 Python 库。让 skill 自己指定镜像和资源配置，是个很自然的需求。

**skill 生态。** manifest 解析、导入导出、远程安装、skill 市场——这些都是更远的事了。先把本地 package 的体验做好。

**和 OpenCode / OpenClaw 的对齐。** 现在的设计已经和 OpenCode 的 `skill + bash/read/edit`、OpenClaw 的 `skills + exec/system.run` 很接近了。后续可以继续观察他们的演进，保持兼容。
