# 博客写作指南

这是公开博客仓库，保存面向读者的技术文章与站点配置。

个人学习记录、简历、面试复盘和作者画像存放在独立的私有仓库，不在本仓库保存。

## 写作风格

具体的写作风格、手法约束、审稿流程和 AI 痕迹检测清单，统一参考 `skills/` 下的相关工作流。

## 文章结构约定

- Jekyll 格式，文件名：`YYYY-M-D-标题.md`
- frontmatter 包含 title, date, categories, tags
- 用 `---` 分隔大章节

## 审稿原则

技术事实必须准确，有疑问时指出而不是放过。论证逻辑要自洽，不要为了得出结论而夸大前提。



## Portable skill layout

- Each skill lives at `.agent/skills/<skill-name>/`.
- `SKILL.md` is the entrypoint and documents the skill in tool-agnostic terms.
- Supporting references and scripts stay beside the skill.
- Skills must not assume a specific agent runtime, hook system, command name, or hidden configuration directory.
- Runtime adapters may call these skills through their own discovery mechanisms.

The author profile and personal source materials live in the separate private profile repository.

