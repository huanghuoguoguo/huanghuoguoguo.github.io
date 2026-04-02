---
title: 'ctfagent：全自动打桩机'
date: 2026-04-01
categories: [工具, AI, CTF]
tags: [ctfagent, Claude Code, Agent, RAG]
---

# ctfagent：全自动打桩机

同学说要打 CTF 比赛，听信了我的话，去 fork 了一个 CTF Agent 项目。

他发了个链接过来：https://github.com/yuanzhiqj/BUUCTF_Agent

一开始他只是问我这玩意为啥部署不上。我让 OpenClaw clone 下来，配环境、跑服务，折腾一通后还真跑起来了，丢给他用。

其实我不懂 CTF。但我点进去看了一眼，界面挺简单：一个网页对话框，输题目标题、描述、目标地址，然后它就自己开始打。

用了两天，他找我：不好用。

我说，我简单看了一下，这项目的 RAG 能增强啊。现在 Chroma 新版本内置了嵌入模型，连 embedding URL 都不用填了，你给作者提个 PR 试试。

再然后，我仔细看了一下它的代码结构。越看越觉得：这不就是一个 RAG 驱动的通用智能体去打 CTF 吗？

那我直接把 RAG 那套拆掉，换成 skills 去驱动 Claude Code，不也一样能打？而且 CC 现在是市面上最强的通用智能体，没理由不用。

ctfagent 就是这么来的。

---

## 核心思路

我现在对 ctfagent 的理解很简单：通用脑子用现成的，领域能力自己补。

Claude Code 本身已经能做对话、分析、调度这些事，也能根据题目类型决定调用哪个 skill。我不想在这一层重复造轮子。

我要补的是 CTF 这层具体能力：稳定的工具接口、漏洞类型对应的 triage 流程、解题经验的沉淀。这些东西收在本地 skills 里，一个 skill 管一类场景。

---

## 为什么不做基于向量的 RAG

我不是说 RAG 完全没用。

如果你要查漏洞定义、工具参数、某篇 writeup 里的一段 payload，检索当然有价值。

我真正保留意见的地方是，很多 CTF 题目更需要“解题链路别断”。检索回来的片段可能是对的，但它经常只能回答“这是什么”，回答不了“现在下一步该干什么”。

我这两天拿 `.ctfagent/targets` 下面那几套本地靶场反复试，体感就更明显了。像 `web-advanced-chain` 这题，前台是个带黑名单的 `/proxy`，会拦 `localhost`、`127.0.0.1` 这类常见写法；后面挂着一个内网服务，里面又有 `/debug?path=` 的任意文件读取和 `/load` 的 pickle 反序列化。你真做的时候，脑子里想的不会是“给我来几段 SSRF 相关文章”，而是：

1. 先确认 SSRF 还能不能打，以及过滤拦的是字符串还是解析后的地址
2. 再想办法摸到内网服务长什么样
3. 摸到之后，先用 `/debug` 读配置和线索
4. 确认后端是 pickle，再构造 payload 去打 `/load`

这条线一断，后面就全断了。光检索到“SSRF”“LFI”“pickle RCE”这几个词，对落题帮助没那么大。

所以我更在意的是怎么把一条完整的做题轨迹留下来。

现在这个记忆大概收在三层：
- 解题过程记录在 `workspaces/<challenge-id>/` 下
- 解出来的题目沉淀到 `knowledge/writeups/`
- 提炼出来的模式写到 `knowledge/patterns/`

下次再碰到类似题，agent 参考的是一条完整链路，而不是从一堆零散片段里临时拼装答案。至少在我现在这个阶段，我更信这种记法。

---

## Skills 组织

ctfagent 目前有 15 个 skills，覆盖 Web、Pwn、知识沉淀、工具支持：

```
.claude/skills/
├── setup/                        # 用户入口
├── ctf-solver-profile/           # 解题策略
├── challenge-workspace-bootstrap/# 题目信息标准化
│
├── web-ssrf-to-rce-triage/       # SSRF → RCE
├── web-sqli-triage/              # SQL 注入
├── web-ssti-triage/              # 模板注入
├── web-jwt-triage/               # JWT
├── web-xss-triage/               # XSS
├── web-deserialization-triage/   # 反序列化
│
├── pwn-initial-recon/            # 二进制分析
├── pwn-stack-overflow-exploit-dev/ # 栈溢出利用
│
├── browser-automation-playwright/ # 浏览器自动化
├── network-search-ddg/           # DuckDuckGo 搜索
│
├── ctf-knowledge-capture/        # 知识沉淀
└── skill-maintainer/             # skill 维护
```

我现在是故意把 skill 拆窄的。

比如 `web-ssrf-to-rce-triage`，就只管 SSRF 这条线：
1. 探测目标能不能 fetch 外部 URL
2. 能的话，尝试 file:// 读文件
3. 找 localhost 才能访问的接口
4. 尝试打 RCE

它不顺手去处理 SQL 注入，也不顺手去碰 XSS。那些交给别的 skill。

我现在越来越接受这种拆法。一个 skill 只管一类漏洞或一个清楚的小任务，Agent 再根据题目上下文决定怎么拼。

---

## 使用方式

使用方式本身没什么花样：

1. 在仓库根目录运行 `/setup`
2. 告诉 agent 题目信息：
   - 题目标题
   - 题目分类
   - 题目描述
   - 目标 URL / 主机 / 端口
   - 附件路径
   - 限制条件

```text
/setup

题目标题：Internal Resource Viewer
分类：web
目标：http://127.0.0.1:8080/
附件：/path/to/app.zip
题目描述：The site previews internal resources.
限制：先做低成本验证，不要直接爆破。
```

如果信息足够，`/setup` 会直接创建 workspace；信息不够，它就先把最小必要字段补齐。

后面 agent 再根据题目类型调用相应的 skill 开始分析。

---

## 已经验证的场景

现在至少在 Web 靶场这类场景里，它已经能跑起来了。我同学拿这套东西去打过靶场，结果能过。

而且现在验证过的不是一套玩具 hello world。`.ctfagent-temp/targets` 下面已经有 SSRF、SQLi、SSTI、JWT、XSS、反序列化，还有两套 Pwn 小靶场。简单的 `web-ssrf-lab` 可以用来验证“先探测能不能出网，再摸内网 flag”这条最短链；复杂一点的 `web-advanced-chain` 则是在逼 agent 把多段漏洞串起来，而不是只认一个知识点标签。

但也就到这里。离“我敢说它已经很通用”还差得远。

目前最现实的卡点，是一些逆向工具的自动化集成还没想好。像 IDA Pro、Ghidra 这种东西，真放进 agent workflow 里，接口应该怎么收、权限怎么控、结果怎么回传，都还得慢慢试。

---

## 工程边界

ctfagent 目前支持：

- Web 类题目：SSRF、SQLi、SSTI、JWT、XSS、反序列化
- Pwn 类题目：二进制初探、栈溢出利用开发
- 支持工具：浏览器自动化、网络搜索

不支持：

- 逆向题目的自动化（IDA Pro 等工具集成还没做）
- Crypto 题目的系统化支持
- 平台自动提交（这块先没做）

---

## 暂时还没想透的地方

**1. 有记忆的 agent 怎么做长期维护**

现在的设计是每道题一个 workspace，解出来的题沉淀到 knowledge/。但题目一多，knowledge 很容易变成另一个垃圾堆。存进去了，不代表真能在下次用上。

**2. CLI 工具集成怎么做**

IDA Pro、Ghidra 这些工具，怎么接进 skill 系统，我现在也还没收住。是直接调命令行，还是包一层中间服务，这里面差别很大。

**3. skill 的数量边界**

现在有 15 个 skills，这个数字肯定还会涨。可涨到什么时候该停，什么粒度才算合适，我还没完全想清楚。至少目前我更倾向于让一个 skill 只负责一类 vulnerability 的 triage，别再往里塞太多相邻职责。

---

> 项目地址：https://github.com/huanghuoguoguo/ctfagent
