---
name: new-or-review
description: 写博客文章或审阅已有文章——按作者画像分阶段写作，调用检测器审查，并做有限轮次修订
---

# 博客写作与审稿

这个 skill 负责两类任务：

- **新建**：从主题到终稿，走完整的 `plan -> draft -> review -> revise -> final-check` 流程
- **审阅**：对现有文章做技术审校、风格审校和 AIGC/author-fit 检测

`SKILL.md` 只保留入口、分流和硬约束。细节全部拆到 `references/`，按需读取，不一次性把整套规则全塞进上下文。

## 与 `author-profile` 的联动

`new-or-review` 负责写作与审稿流程，不负责单独维护“作者是谁”。作者画像、稳定偏好、认知转折素材的系统记录，以 `.claude/skills/author-profile` 为准。

联动规则：

1. 写作或审稿前，先把 `author-profile` 当成事实源：
   - `.claude/skills/author-profile/PROFILE.md`
   - `_not_publish/经历与思考素材库.md`
   - 相关经历文件或 `_not_publish/jianli.md`
2. `references/author-constraints.md` 是写作时的操作化约束，不是独立画像源。
3. 如果和 `author-profile` 里的记录冲突，以 `author-profile` 为准；需要时再同步更新本 skill 的约束镜像。
4. 在 interview、review、revise 过程中，如果拿到了新的稳定信息，默认自动判断并回写给 `author-profile`，不需要在当前任务里单独征求确认；只有在记录冲突、会覆盖既有画像、或事实来源不足时，才暂停并提示用户：
   - 稳定风格偏好 / 思考方式 -> `author-profile/PROFILE.md`
   - 可复用的认知转折 / 原话 / 场景 -> `_not_publish/经历与思考素材库.md`
   - 项目事实、指标、职责边界 -> 对应经历文件或 `_not_publish/jianli.md`
5. 检测器信号、AI 推测、一次性润色策略，默认不能直接写入画像；只有用户明确表述、用户真实改稿、或足够稳定的反复偏好，才允许沉淀。

## 目录

- `references/author-constraints.md`
  - 作者画像、知识边界、写作硬约束、稳定表达偏好

- `references/new-post-workflow.md`
  - 新建文章的 `Stage 0 -> Stage 5`

- `references/review-and-revise.md`
  - 技术事实检查、风格检查、检测器调用、revision plan、停止条件

- `references/article-types.md`
  - 技术深潜、系统设计、读书笔记、实践复盘的骨架

- `references/anti-patterns.md`
  - 高频 AI 痕迹、模板化过渡、禁用词和改写方向

- `references/style-extraction-method.md`
  - 如何从样本文本里提取文风，如何练习模仿，而不是只学表面句式

- `references/xiaolin-style.md`
  - 基于 `samples/xiaolin.md` 和 `samples/xiaolin2.md` 提取的小林文风样本卡片，以及“借骨架不借人格”的适配规则

- `references/xiaolin-adaptation-template.md`
  - “借小林骨架，但仍然是作者本人”的提纲模板、写作提示词骨架和审稿自检清单

## 运行时依赖

- `tools/ai-writing-bad-cases-app/`
  - 外部检测器仓库；相对当前 skill 目录解析

- `samples/xiaolin.md`
  - 小林样本文本 1；用于重新提取或校准文风卡片

- `samples/xiaolin2.md`
  - 小林样本文本 2；用于重新提取或校准文风卡片

依赖缺失时：

- 不得假装已经调用检测器或已经读取原始样本
- 必须明确报告缺失了哪个相对路径
- 可以继续使用 `references/` 里的沉淀卡片做有限分析，但不能冒充做了完整依赖流程

## 使用顺序

### 新建文章

1. 先读 `.claude/skills/author-profile/PROFILE.md`
2. 再读 `_not_publish/经历与思考素材库.md`
3. 如果主题涉及具体项目，再读相关经历文件或 `_not_publish/jianli.md`
4. 再读 `references/author-constraints.md`
5. 再读 `references/new-post-workflow.md`
6. 根据文章类型按需读 `references/article-types.md`
7. 如果用户明确要求模仿某种文风，读 `references/style-extraction-method.md` 和对应样本卡片
8. 如果需要重新提取或校准小林文风卡片，再读 `samples/xiaolin.md` 和 `samples/xiaolin2.md`
9. 如果是“像小林，但内容仍然是我自己的”，再读 `references/xiaolin-adaptation-template.md`
10. 首稿完成后读 `references/review-and-revise.md`
11. 如果有明显套话或模板味，再补读 `references/anti-patterns.md`
12. 如果本轮暴露了新的稳定偏好或素材，回写 `author-profile`

### 审阅现有文章

1. 先读 `.claude/skills/author-profile/PROFILE.md`
2. 必要时读 `_not_publish/经历与思考素材库.md`
3. 再读 `references/author-constraints.md`
4. 再读 `references/review-and-revise.md`
5. 若问题集中在模板味、AI 味、结尾过度收束，再读 `references/anti-patterns.md`
6. 如果用户要求“像某个作者/样本”，再读对应样本卡片
7. 如果用户要求“像小林，但还是我自己”，再读 `references/xiaolin-adaptation-template.md`
8. 如果用户真实改稿暴露了新的稳定偏好，回写 `author-profile`

### 提取或学习文风

1. 先读 `references/style-extraction-method.md`
2. 如果要重新提取或更新卡片，先读原始样本，例如 `samples/xiaolin.md` 和 `samples/xiaolin2.md`
3. 再读已有样本卡片，例如 `references/xiaolin-style.md`
4. 输出时区分：
   - `可观察特征`
   - `推测性偏好`
   - `可训练动作`
5. 不把样本的主题、口头禅、格式习惯误当成全部文风

## 不可违反的规则

1. 不让 AI 一步到位写完整篇文章。
2. 检测器负责指出问题，不负责代写终稿。
3. 修订时只改命中的段落，不整篇重写。
4. 自动回环最多 2 到 3 轮，之后交给人工裁决。
5. 只要存在认知边界、材料缺口、叙述方式不确定，先访谈，不硬写。
6. 篇级句法限额要当硬约束处理：整篇文章里，“不是……而是……”最多出现 1 次，“回头看”最多出现 1 次；超出就按模板化写作处理并优先改掉。

## 检测器

检测器仓库：`tools/ai-writing-bad-cases-app/`（相对当前 skill 目录）

这是运行时依赖。缺失时，必须明确报告“检测器不可用”，不能声称已经完成检测器审查。

检测器只负责：

- 找出 AIGC 痕迹
- 找出和作者风格不一致的地方
- 给出段落级证据、风险和改写方向

检测器不负责：

- 定义本 skill 的写作 prompt
- 直接产出最终文章
- 决定整篇文章的最终取舍

## 输出原则

- 首先报告证据和判断，不先端漂亮结论
- 允许局部不确定，但不能把不确定写成事实
- 优先保留作者自己的材料、火气、犹豫和认知来路
- 需要回访作者时，明确列出少量关键问题，不铺满
