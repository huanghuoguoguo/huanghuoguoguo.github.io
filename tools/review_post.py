#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DETECTOR_ROOT = Path("/home/yhh/learn/ai-writing-bad-cases-app")
DEFAULT_STYLE_GUIDE = Path("/home/yhh/learn/huanghuoguoguo.github.io/CLAUDE.md")


@dataclass
class Paragraph:
    index: int
    start_line: int
    text: str


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return text
    return parts[1]


def _normalize_inline_markdown(line: str) -> str:
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"`([^`]+)`", r"\1", line)
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^[-*+]\s+", "", line)
    line = re.sub(r"^\d+\.\s+", "", line)
    line = re.sub(r"\{[%{].*?[}%]\}", "", line)
    return line.strip()


def extract_paragraphs(post_path: Path) -> list[Paragraph]:
    raw_text = post_path.read_text(encoding="utf-8")
    text = _strip_frontmatter(raw_text)
    lines = text.splitlines()

    paragraphs: list[Paragraph] = []
    buffer: list[str] = []
    start_line: int | None = None
    in_code_fence = False

    def flush() -> None:
        nonlocal buffer, start_line
        if not buffer or start_line is None:
            buffer = []
            start_line = None
            return
        normalized = " ".join(part for part in buffer if part).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if normalized:
            paragraphs.append(
                Paragraph(
                    index=len(paragraphs),
                    start_line=start_line,
                    text=normalized,
                )
            )
        buffer = []
        start_line = None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            flush()
            continue
        if in_code_fence:
            continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("{%") or stripped.startswith("%{"):
            continue

        normalized = _normalize_inline_markdown(line)
        if not normalized:
            continue
        if start_line is None:
            start_line = lineno
        buffer.append(normalized)

    flush()
    return paragraphs


def run_detector(paragraphs: list[Paragraph], detector_root: Path) -> dict[str, Any]:
    normalized_text = "\n\n".join(paragraph.text for paragraph in paragraphs)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(normalized_text)
        tmp_path = Path(tmp.name)

    command = [
        "uv",
        "run",
        "python",
        "-m",
        "ai_badcase_app.cli",
        "--input",
        str(tmp_path),
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=detector_root,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return json.loads(completed.stdout)


def _strategy_for_signal(code: str) -> str:
    code = code.lower()
    if "conclusion" in code or "summary" in code:
        return "删掉结论先行的总结句，停在具体观察或细节处。"
    if "connector" in code or "transition" in code:
        return "去掉逻辑胶水词，直接改写成自然推进的叙述。"
    if "lexical" in code or "repeat" in code:
        return "换掉重复词，优先补具体动作和对象，不靠同义词堆砌。"
    if "sentence" in code or "variation" in code:
        return "打散节奏，拆长句，允许短句和停顿。"
    if "passive" in code:
        return "改为主动表达，把谁做了什么写清楚。"
    return "回到具体场景、证据和你的真实判断，不要继续抽象总结。"


def build_revision_plan(report: dict[str, Any], paragraphs: list[Paragraph]) -> dict[str, Any]:
    paragraph_lookup = {paragraph.index: paragraph for paragraph in paragraphs}
    reviewed: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()

    for item in report.get("paragraphs", []):
        paragraph_index = item.get("paragraph_index")
        source_paragraph = paragraph_lookup.get(paragraph_index)
        actions: list[str] = []
        for signal in item.get("signals", []):
            code = signal.get("code", "unknown")
            issue_counter[code] += 1
            action = _strategy_for_signal(code)
            if action not in actions:
                actions.append(action)
        reviewed.append(
            {
                "paragraph_index": paragraph_index,
                "start_line": source_paragraph.start_line if source_paragraph else None,
                "risk_score": item.get("risk_score", 0.0),
                "risk_level": item.get("risk_level", "low"),
                "text_excerpt": item.get("text_excerpt", ""),
                "signals": item.get("signals", []),
                "rewrite_hints": item.get("rewrite_hints", []),
                "actions": actions,
            }
        )

    top_codes = [code for code, _ in issue_counter.most_common(5)]
    return {
        "document_score": report.get("document_score", {}),
        "summary": report.get("summary", {}),
        "top_issue_codes": top_codes,
        "paragraphs": reviewed,
    }


def _load_style_guide(style_guide_path: Path) -> str:
    if not style_guide_path.exists():
        return ""
    text = style_guide_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    return "\n".join(lines[:40])


def run_claude_rewrite(plan: dict[str, Any], style_guide_path: Path, max_paragraphs: int) -> list[dict[str, Any]]:
    style_guide = _load_style_guide(style_guide_path)
    rewrites: list[dict[str, Any]] = []
    candidates = sorted(
        plan["paragraphs"],
        key=lambda item: item.get("risk_score", 0.0),
        reverse=True,
    )[:max_paragraphs]

    for candidate in candidates:
        prompt = f"""你是技术博客编辑。目标是把下面这段话改得更像作者本人，而不是更像'自然语言模型'。\n\n作者风格约束：\n{style_guide}\n\n原段落：\n{candidate['text_excerpt']}\n\n检测到的问题：\n{json.dumps(candidate['signals'], ensure_ascii=False, indent=2)}\n\n要求：\n1. 保留原意，不引入没证据的新事实。\n2. 写成更口语、短句、具体的技术散文。\n3. 少总结，少模板化过渡。\n4. 如果原文太空，就把表达收窄，而不是胡乱补细节。\n\n请只输出 JSON，格式如下：\n{{\n  \"rewrite\": \"改写后的单段文本\",\n  \"why\": [\"修改原因1\", \"修改原因2\"]\n}}"""
        completed = subprocess.run(
            ["claude", "-p", prompt],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = completed.stdout.strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"rewrite": payload, "why": ["Claude 没有按 JSON 返回，已保留原始输出。"]}
        rewrites.append(
            {
                "paragraph_index": candidate["paragraph_index"],
                "start_line": candidate["start_line"],
                "rewrite": parsed.get("rewrite", ""),
                "why": parsed.get("why", []),
            }
        )
    return rewrites


def render_markdown(post_path: Path, plan: dict[str, Any], rewrites: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"# Review Report: {post_path.name}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    document_score = plan.get("document_score", {})
    summary = plan.get("summary", {})
    lines.append(f"- overall_risk: {document_score.get('overall_risk', 0.0)}")
    lines.append(f"- author_fit: {document_score.get('author_fit', 0.0)}")
    lines.append(f"- stop_or_retry: {summary.get('stop_or_retry', 'unknown')}")
    if plan.get("top_issue_codes"):
        lines.append(f"- top_issue_codes: {', '.join(plan['top_issue_codes'])}")
    lines.append("")
    lines.append("## Paragraph Findings")
    lines.append("")
    for item in plan["paragraphs"]:
        lines.append(
            f"### Paragraph {item['paragraph_index']} (line {item['start_line']}, risk={item['risk_score']}, level={item['risk_level']})"
        )
        lines.append("")
        lines.append(item["text_excerpt"])
        lines.append("")
        lines.append("Signals:")
        for signal in item["signals"]:
            lines.append(
                f"- `{signal.get('code', 'unknown')}`: {signal.get('reason', '')} | hint: {signal.get('rewrite_hint', '')}"
            )
        if item["actions"]:
            lines.append("Actions:")
            for action in item["actions"]:
                lines.append(f"- {action}")
        lines.append("")

    if rewrites:
        lines.append("## Claude Rewrite Samples")
        lines.append("")
        for rewrite in rewrites:
            lines.append(
                f"### Paragraph {rewrite['paragraph_index']} (line {rewrite['start_line']})"
            )
            lines.append("")
            lines.append(rewrite["rewrite"])
            lines.append("")
            for reason in rewrite.get("why", []):
                lines.append(f"- {reason}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a blog post with the bad-case detector")
    parser.add_argument("post_path", help="Path to the markdown post")
    parser.add_argument(
        "--detector-root",
        default=str(DEFAULT_DETECTOR_ROOT),
        help="Path to the detector repository",
    )
    parser.add_argument(
        "--style-guide",
        default=str(DEFAULT_STYLE_GUIDE),
        help="Path to the blog style guide",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the markdown report",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path to write the structured review JSON",
    )
    parser.add_argument(
        "--with-claude",
        action="store_true",
        help="Ask Claude Code for rewrite samples on the highest-risk paragraphs",
    )
    parser.add_argument(
        "--max-rewrites",
        type=int,
        default=2,
        help="How many paragraphs to send to Claude when --with-claude is enabled",
    )
    args = parser.parse_args()

    post_path = Path(args.post_path).resolve()
    detector_root = Path(args.detector_root).resolve()
    style_guide_path = Path(args.style_guide).resolve()

    paragraphs = extract_paragraphs(post_path)
    report = run_detector(paragraphs, detector_root)
    plan = build_revision_plan(report, paragraphs)
    rewrites = run_claude_rewrite(plan, style_guide_path, args.max_rewrites) if args.with_claude else []

    rendered = render_markdown(post_path, plan, rewrites)

    if args.json_output:
        json_path = Path(args.json_output).resolve()
        json_path.write_text(
            json.dumps({"detector_report": report, "revision_plan": plan, "claude_rewrites": rewrites}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
