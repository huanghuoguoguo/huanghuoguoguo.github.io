#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / ".claude" / "skills" / "author-profile").is_dir()
            and (candidate / "_not_publish").is_dir()
        ):
            return candidate
    raise RuntimeError(
        f"无法从脚本路径推断仓库根目录: {start}. "
        "期望同时找到 .claude/skills/author-profile 和 _not_publish"
    )


ROOT = _find_repo_root(Path(__file__).parent)
SKILL_DIR = ROOT / ".claude" / "skills" / "author-profile"
PROFILE = SKILL_DIR / "PROFILE.md"
MATERIALS = ROOT / "_not_publish" / "经历与思考素材库.md"
EXPERIENCE_FILES = [
    ROOT / "_not_publish" / "中科曙光经历.md",
    ROOT / "_not_publish" / "蚂蚁金服ob经历.md",
    ROOT / "_not_publish" / "jianli.md",
]

REQUIRED_CARD_FIELDS = [
    "时间",
    "地点 / 项目",
    "我当时在做什么",
    "我先入为主怎么想",
    "真正出问题的地方",
    "我怎么发现的",
    "我后来怎么改",
    "这件事让我现在更相信什么",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"`+", "", text)
    text = re.sub(r"[：:，,。.!！？?（）()\-\s]+", "", text)
    return text


def _extract_bullets_by_section(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        elif current and line.startswith("- "):
            sections[current].append(line[2:].strip())
    return sections


def check_profile() -> list[str]:
    issues: list[str] = []
    text = _read(PROFILE)
    if not text:
        return ["missing: PROFILE.md 不存在"]

    line_count = len(text.splitlines())
    if line_count > 170:
        issues.append(f"profile-too-long: PROFILE.md 当前 {line_count} 行，已经偏长")

    sections = _extract_bullets_by_section(text)
    for section, bullets in sections.items():
        seen: dict[str, str] = {}
        for bullet in bullets:
            key = _norm(bullet)
            if not key:
                continue
            if key in seen:
                issues.append(
                    f"profile-duplicate: 节 {section} 下有重复/近重复条目 -> {bullet}"
                )
            else:
                seen[key] = bullet
    return issues


def _split_cards(text: str) -> list[tuple[str, str]]:
    cards: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("### "):
            if current_title:
                cards.append((current_title, "\n".join(current_lines)))
            current_title = line[4:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)
    if current_title:
        cards.append((current_title, "\n".join(current_lines)))
    return cards


def check_materials() -> list[str]:
    issues: list[str] = []
    text = _read(MATERIALS)
    if not text:
        return ["missing: 经历与思考素材库.md 不存在"]

    cards = _split_cards(text)
    seen_titles: set[str] = set()
    for title, body in cards:
        if title == "标题":
            continue
        norm_title = _norm(title)
        if norm_title in seen_titles:
            issues.append(f"materials-duplicate-title: 素材卡片标题重复 -> {title}")
        seen_titles.add(norm_title)

        for field in REQUIRED_CARD_FIELDS:
            marker = f"- {field}："
            if marker not in body:
                issues.append(f"materials-missing-field: 卡片《{title}》缺少字段 {field}")
    return issues


def check_experience_files() -> list[str]:
    issues: list[str] = []
    for path in EXPERIENCE_FILES:
        text = _read(path)
        if not text:
            issues.append(f"missing: {path.name} 不存在")
            continue
        if "## " not in text:
            issues.append(f"experience-structure: {path.name} 缺少二级标题，结构可能有问题")
        if path.name != "jianli.md" and "面试准备要点" not in text:
            issues.append(f"experience-missing-review: {path.name} 没有面试准备要点，后续复用可能不方便")
    return issues


def main() -> None:
    issues = [
        *check_profile(),
        *check_materials(),
        *check_experience_files(),
    ]
    if not issues:
        print("OK: author-profile files look consistent")
        return

    print("WARN: author-profile maintenance issues found")
    for item in issues:
        print(f"- {item}")


if __name__ == "__main__":
    main()
