# 博客写作指南

## 作者画像
- 系统方向的软件工程师，参加过 OceanBase 数据库大赛（向量索引优化）
- 知识面：Linux 内核、性能工程（eBPF/perf）、并发模型、分布式系统、JVM、数据库内核
- 当前阶段：研究生，正在写大论文

## 写作风格

具体的写作风格、手法约束、审稿流程和 AI 痕迹检测清单，不在这里重复维护。

统一参考：

- `/new-or-review`
- `.claude/skills/new-or-review/SKILL.md`

## 文章结构约定
- Jekyll 格式，文件名：`YYYY-M-D-标题.md`
- frontmatter 包含 title, date, categories, tags
- 用 `---` 分隔大章节
- 代码块标注语言类型

## 可用 Skills

| 命令 | 说明 |
|------|------|
| `/new-or-review` | 写博客文章或审阅已有文章——创建骨架、写作、技术审校、AI 痕迹检测 |
| `/link-posts` | 查找当前文章与已有博文的关联，生成交叉引用 |
| `/author-profile` | 维护作者画像，随交互动态更新 `.claude/skills/author-profile/PROFILE.md` |

详细定义见 `.claude/skills/<skill-name>/SKILL.md`。

## 审稿原则
- 技术事实必须准确，有疑问时指出而不是放过
- 论证逻辑要自洽，不要为了得出结论而夸大前提（如 RAG 文章的向量更新问题）
- 对我的文章保持批判性，发现不对的地方直接说
