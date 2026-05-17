#!/usr/bin/env python3
"""Lightweight review signal scanner for blog drafts.

This script does not decide whether an article is good. It only surfaces
programmable hints that are easy to miss during a long review pass.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


CLICHE_PHRASES = [
    "本质上",
    "毋庸置疑",
    "显而易见",
    "众所周知",
    "值得注意的是",
    "不可否认",
    "换句话说",
    "总的来说",
    "综上所述",
    "由此可见",
    "在这个过程中",
    "从某种意义上",
]

FORCED_SUMMARY_PHRASES = [
    "这就是",
    "这也说明",
    "这让我意识到",
    "所以说",
    "归根结底",
    "最终",
    "总结下来",
    "真正重要的是",
]

NARRATIVE_TICKS = [
    "后来才发现",
    "后来才意识到",
    "后来才明白",
    "后来慢慢",
    "回头看",
]

HEDGE_PHRASES = [
    "按我现在",
    "按我现在的理解",
    "我更愿意把",
    "我更倾向于",
    "某种意义上",
]

DASH_RE = re.compile(r"——|—")

INTERVIEW_MARKERS = [
    "TODO",
    "待补",
    "这里需要补",
    "这里还没想清楚",
    "不确定",
    "记不清",
]

TECH_MARKERS = [
    "数据库",
    "缓存",
    "系统",
    "架构",
    "接口",
    "线程",
    "内存",
    "内核",
    "分布式",
    "可观测",
    "性能",
    "延迟",
    "吞吐",
    "OceanBase",
    "Redis",
    "MySQL",
    "Linux",
]

HARD_EVIDENCE_RE = re.compile(
    r"```|`[^`]+`|\b\d+(\.\d+)?\s*(ms|s|秒|分钟|%|KB|MB|GB|QPS|TPS)\b|"
    r"benchmark|perf|trace|日志|命令|输出|火焰图|对比表|curl|pytest|go test|EXPLAIN",
    re.IGNORECASE,
)

SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;]\s*")


def paragraph_blocks(text: str) -> list[dict]:
    blocks = []
    current = []
    start_line = 1

    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not current:
                start_line = line_no
            current.append(line.rstrip())
        elif current:
            blocks.append(
                {
                    "line": start_line,
                    "end_line": line_no - 1,
                    "text": "\n".join(current).strip(),
                }
            )
            current = []

    if current:
        blocks.append(
            {
                "line": start_line,
                "end_line": len(text.splitlines()),
                "text": "\n".join(current).strip(),
            }
        )

    return blocks


def snippet(text: str, limit: int = 120) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 1] + "..."


def add_signal(signals: list[dict], kind: str, severity: str, block: dict | None, evidence: str, why: str, suggestion: str) -> None:
    signal = {
        "type": kind,
        "severity": severity,
        "evidence": snippet(evidence),
        "why": why,
        "suggestion": suggestion,
    }
    if block:
        signal["line"] = block["line"]
        signal["end_line"] = block["end_line"]
    signals.append(signal)


def scan_paragraphs(blocks: list[dict]) -> list[dict]:
    signals: list[dict] = []

    for block in blocks:
        text = block["text"]
        if text.startswith("#"):
            continue
        if text.strip() == "---":
            continue

        dash_hits = DASH_RE.findall(text)
        if dash_hits:
            add_signal(
                signals,
                "dash_usage",
                "warning",
                block,
                text,
                "破折号容易制造解释、升格或金句感；在这类博客里会让判断显得被包装过。",
                "默认删除破折号。不要机械换成逗号；先判断两边关系，再拆句、改成冒号、括号说明，或重写成更直接的判断。",
            )

        hits = [phrase for phrase in CLICHE_PHRASES if phrase in text]
        if hits:
            add_signal(
                signals,
                "cliche_phrase",
                "warning",
                block,
                "、".join(hits),
                "命中常见模板词，容易让判断显得像套话。",
                "删除套话，直接写具体观察、动作、数据或场景。",
            )

        tail = text[-90:]
        forced_hits = [phrase for phrase in FORCED_SUMMARY_PHRASES if phrase in tail]
        if forced_hits:
            add_signal(
                signals,
                "forced_summary",
                "warning",
                block,
                tail,
                "段落末尾可能在强行收束，容易把真实过程压成漂亮结论。",
                "让段落停在具体细节、问题或下一步动作上，不急着升华。",
            )

        has_broad_claim = any(word in text for word in ["本质", "关键", "核心", "必须", "一定", "证明", "说明", "显著", "根因"])
        if has_broad_claim and not HARD_EVIDENCE_RE.search(text):
            add_signal(
                signals,
                "missing_evidence",
                "warning",
                block,
                text,
                "这一段有偏强的判断，但缺少命令、日志、数据、案例或明确场景支撑。",
                "补具体证据；如果没有证据，就收窄结论或改成待验证判断。",
            )

        interview_hits = [phrase for phrase in INTERVIEW_MARKERS if phrase in text]
        if interview_hits:
            add_signal(
                signals,
                "need_interview",
                "error",
                block,
                "、".join(interview_hits),
                "这里暴露了材料缺口，继续润色可能会用常识替作者补事实。",
                "停下来回访作者，补场景、边界、数据或真实认知来路。",
            )

    return signals


def scan_article_level(text: str, blocks: list[dict]) -> list[dict]:
    signals: list[dict] = []

    tick_count = sum(text.count(phrase) for phrase in NARRATIVE_TICKS)
    if tick_count > 2:
        add_signal(
            signals,
            "narrative_tick",
            "warning",
            None,
            f"count={tick_count}",
            "认知转折提示词出现过多，文章节奏可能变成可预测的成长叙事。",
            "把部分转折改成具体触发事件、数据、对话或报错。",
        )

    hedge_count = sum(text.count(phrase) for phrase in HEDGE_PHRASES)
    if hedge_count > 1:
        add_signal(
            signals,
            "hedge_habit",
            "warning",
            None,
            f"count={hedge_count}",
            "缓冲判断的表达出现过多，会削弱作者判断的锋利度。",
            "只保留真正需要限定的一处，其余地方直接下判断或给出具体限定来源。",
        )

    formula_markers = ["原来", "一开始", "后来", "现在", "最后", "最终"]
    formula_blocks = [b for b in blocks if sum(1 for marker in formula_markers if marker in b["text"]) >= 2]
    if len(formula_blocks) >= 3:
        add_signal(
            signals,
            "cognitive_formula",
            "warning",
            None,
            f"paragraphs={len(formula_blocks)}",
            "多段共享同一套认知弧，文章可能从真实复盘滑向公式化成长叙事。",
            "至少让一处转折由外部锚点推动，例如数据、对话、报错或一次失败。",
        )

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if len(s.strip()) >= 8]
    lengths = [len(re.sub(r"\s+", "", s)) for s in sentences]
    if len(lengths) >= 10:
        mean = statistics.mean(lengths)
        stdev = statistics.pstdev(lengths)
        if mean >= 18 and stdev / mean < 0.28:
            add_signal(
                signals,
                "uniform_sentence_length",
                "info",
                None,
                f"sentences={len(lengths)}, mean={mean:.1f}, stdev={stdev:.1f}",
                "句长分布过于平均，读起来可能太平、太整齐。",
                "拆出几个短句，保留停顿、犹豫和更口语的转折。",
            )

    is_technical = any(marker in text for marker in TECH_MARKERS)
    has_hard_evidence = bool(HARD_EVIDENCE_RE.search(text))
    if is_technical and not has_hard_evidence:
        add_signal(
            signals,
            "no_hard_evidence",
            "error",
            None,
            "technical markers present, hard evidence absent",
            "文章像技术深潜或系统设计，但全文没有明显硬证据。",
            "补命令输出、日志片段、benchmark、性能数字或对比表；没有就收窄结论。",
        )

    return signals


def mask_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            masked = [""] * (index + 1) + lines[index + 1 :]
            return "\n".join(masked)

    return text


def classify_ai_trace(signals: list[dict]) -> str:
    weighted = 0
    for signal in signals:
        weighted += {"error": 3, "warning": 2, "info": 1}.get(signal["severity"], 1)
    if weighted >= 12:
        return "重"
    if weighted >= 5:
        return "中"
    return "轻"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a Markdown draft for lightweight review signals.")
    parser.add_argument("article", help="Path to the Markdown article or draft.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    article_path = Path(args.article)
    text = mask_frontmatter(article_path.read_text(encoding="utf-8"))
    blocks = paragraph_blocks(text)
    signals = scan_paragraphs(blocks) + scan_article_level(text, blocks)

    result = {
        "file": str(article_path),
        "summary": {
            "signal_count": len(signals),
            "ai_trace_level": classify_ai_trace(signals),
            "error_count": sum(1 for signal in signals if signal["severity"] == "error"),
            "warning_count": sum(1 for signal in signals if signal["severity"] == "warning"),
            "info_count": sum(1 for signal in signals if signal["severity"] == "info"),
        },
        "signals": signals,
        "note": "Signals are review hints, not verdicts. Confirm every item against author-profile and the article context.",
    }

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
