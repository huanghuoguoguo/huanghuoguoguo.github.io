# scripts

这里放 skill 内部的轻量程序化检查脚本。

当前脚本：

- `review_signals.py`
  - 扫描 Markdown 草稿中的模板词、强行总结、句长过匀、认知转折节拍、证据缺失等信号
  - 输出 JSON，供 `references/review-and-revise.md` 里的 review 流程使用

使用示例：

```bash
py .claude/skills/new-or-review/scripts/review_signals.py path/to/article.md --pretty
```

如果环境里的 `python` 命令可用，也可以把 `py` 换成 `python`。

脚本输出只是审稿线索，不是判决。每个命中项都需要结合 `author-profile`、文章上下文和人工判断再决定是否修改。
