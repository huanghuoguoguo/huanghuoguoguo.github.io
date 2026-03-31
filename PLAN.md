# Blog Agent Plan

更新时间：2026-03-25

## 目标

把博客仓库里的写作流程从“让 AI 直接写一篇文章”改成“按作者画像分阶段写，再经过检测回环做局部修订”。

核心目标：

- 写得像作者本人
- 技术上站得住
- 保留实验、命令、图示和迭代痕迹
- 自动化只做有限轮次，最后保留人工裁决

## 输入约束

写作 agent 必须遵守以下来源：

- [`CLAUDE.md`](/home/yhh/learn/huanghuoguoguo.github.io/CLAUDE.md)
- [`SKILL.md`](/home/yhh/learn/huanghuoguoguo.github.io/.claude/skills/new-or-review/SKILL.md)
- 已有 `_posts/` 作为风格参考

重点遵守：

- 开头从问题或场景切入
- 用 benchmark、命令输出、syscall 计数等证据说话
- 接受 V1 到 V2 到 V3 的真实演化，不强行整理成完美阶梯
- 句子短，允许闲笔
- 结尾不强迫升华

## 工作流

### Stage 1：Plan

输入：

- 题目
- 文章类型
- 目标读者
- 原始素材

输出：

- 文章论证路线
- 章节骨架
- 证据缺口列表
- 哪些地方必须补实验或命令

要求：

- 先出骨架，不直接出终稿
- 如果主题超出知识边界，明确收窄论述范围

### Stage 2：Draft

基于骨架生成首稿：

- frontmatter 正确
- 每节围绕一个具体问题
- 尽量落到命令、数据、对比、ASCII 图
- 不主动写满所有结论

首稿不是终稿，允许有不完美处，但必须有真实材料支撑点。

### Stage 3：Review

输入首稿后，执行三类检查：

1. 技术事实检查
2. 作者风格检查
3. 调用 `ai-writing-bad-cases-app` 做结构化检测

输出：

- revision plan
- 高优先级问题
- 哪些段落该删，哪些该补证据，哪些只需微调语气

### Stage 4：Revise

只对命中的段落做局部修改：

- 删套话
- 补具体例子和实验
- 拆长句
- 打散机械过渡
- 放回真实的犹豫和边界

禁止每一轮整篇重写。

### Stage 5：Final Check

再跑一次检测，决定：

- `accept`
- `retry`
- `handoff_to_human`

最多自动循环 2 到 3 轮。

## 与检测器的接口

博客仓库不应该自己解析原始规则，而应消费检测器 JSON：

- 按 `paragraph_index` 定位问题
- 按 `signals[].code` 选择修订策略
- 按 `severity` 排定优先级
- 按 `summary.stop_or_retry` 决定继续还是停止

## 修订策略映射

建议维护一份内部映射表：

- `cliche_phrase` -> 删套话，直接进入事实或观察
- `forced_summary` -> 删除节尾抽象总结，停在细节处
- `uniform_sentence_length` -> 打散节奏，加入短句和停顿
- `missing_evidence` -> 补命令、数据、图、日志
- `perfect_ladder` -> 恢复真实迭代过程，不要硬凑线性胜利
- `author_fit_low` -> 回到作者画像，收窄语气和知识边界

## 近期里程碑

### Milestone 1：工作流拆分

- 把现在的 `/new-or-review` 细化成 `plan/draft/review/revise/final-check`
- 明确每阶段输入输出
- 让“检测”成为正式阶段，而不是最后随手看一眼

### Milestone 2：接入检测器

- 固定检测器调用方式
- 读取 JSON 输出
- 生成 revision plan

### Milestone 3：提升像作者的程度

- 从已有文章里抽出正样本特征
- 让 review 阶段显式检查“有没有你的味道”
- 增加人工最终裁决模板

## 停止条件

自动循环必须停止于以下任一条件：

- 高严重度问题已清空
- 两轮后总分变化很小
- 修订开始删除真实细节
- 文章已经“没 AI 味，但也没你味”

最后一种尤其要警惕。

## 不做的事

- 不追求一次生成直接完稿
- 不为了过检测把文章改得油滑、空洞
- 不引入作者不熟的技术名词硬撑场面
- 不把所有问题都交给自动改写解决

## 验收标准

- 首稿到终稿的修改理由清楚
- 检测结果能转成可执行 revision plan
- 终稿保留作者真实语气和技术边界
- 对同一主题，系统能稳定产出“可救”的初稿，而不是随机成文
