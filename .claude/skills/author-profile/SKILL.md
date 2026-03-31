---
name: author-profile
description: 维护作者画像、经历、思考方式和写作偏好；当用户聊到项目、实习、读书、写作修改、面试复盘时，自动把高价值信息沉淀到 PROFILE.md 与素材库，并和未发布经历文件互相校准
---

# 作者画像维护

这个 skill 不做“人设包装”，只负责维护稳定事实、技术判断、思考方式、写作偏好，以及可复用的认知转折素材。

`SKILL.md` 只保留入口、分流和硬约束。细节拆到 `references/`，按需读取，不一次性把整套维护规则灌进上下文。

## 目标

- 让 agent 越聊越像认识这个作者，而不是每次从零猜
- 让写博客时能调到“只有作者自己能写”的材料
- 让作者画像、经历文件、素材库三者互相校准，不越记越乱

## 与 `new-or-review` 的边界

`author-profile` 负责系统记录作者是谁，以及哪些材料可长期复用。

- `author-profile` 负责：
  - 维护稳定事实、长期偏好、认知转折素材、经历文件校准
- `new-or-review` 负责：
  - 访谈、列提纲、写首稿、审稿、调用检测器、做局部修订

如果两个 skill 的描述冲突，以这里维护的画像和素材文件为准；`new-or-review` 里的作者约束只是操作化镜像，不是独立真相源。

## 目录

- `PROFILE.md`
  - 高密度作者画像。要求短、稳、去重，控制在 150 行左右

- `scripts/check_author_profile.py`
  - 轻量一致性检查。完成维护后运行一次

- `references/file-map-and-boundaries.md`
  - 核心文件地图、和 `new-or-review` 的职责边界、默认读文件顺序

- `references/trigger-and-deposition.md`
  - 什么时候触发、什么时候不触发、三层沉淀模型、更新原则

- `references/extraction-and-writeback.md`
  - 如何从对话里分类信息、如何决定落点、如何处理来自写作/改稿任务的回写

- `references/maintenance-checklist.md`
  - 固定 checklist、决策树、冲突处理、写入风格、禁止事项和成功标准

## 使用顺序

1. 先读 `PROFILE.md`
2. 再读 `references/file-map-and-boundaries.md`
3. 根据当前任务，按需补读：
   - 判断要不要触发、信息该落哪层：`references/trigger-and-deposition.md`
   - 需要分类、落点、回写写作任务信息：`references/extraction-and-writeback.md`
   - 需要完整过一遍 checklist 或做最终自检：`references/maintenance-checklist.md`
4. 如任务涉及具体项目、简历或素材，再读对应经历文件或 `_not_publish/经历与思考素材库.md`
5. 如有更新，运行：
   - `python3 .claude/skills/author-profile/scripts/check_author_profile.py`

## 默认执行流

1. 先判断本轮有没有新信息
2. 再判断信息属于哪一类、该落哪一层
3. 最后才做最小更新
4. 有更新才跑检查脚本
5. 没有新信息就不改

## 不可违反的规则

1. 只记事实和一手判断，不记没有把握的推测。
2. PROFILE 写稳定特征，素材库写认知过程，经历文件写事实边界，不混写。
3. 不要把一次吐槽、一次情绪或一次临时策略直接升级成稳定画像。
4. 不要把作者包装成全知视角，也不要假设用户讲过一个项目就完全掌握所有底层细节。
5. 更新时优先做最小改动，不大面积重写。
6. 如果本轮更新了文件，结束前必须跑检查脚本；脚本报 warning 时，先修结构问题。
