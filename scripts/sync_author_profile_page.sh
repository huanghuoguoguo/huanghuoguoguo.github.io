#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_FILE="${REPO_ROOT}/_tabs/about.md"

cat > "${TARGET_FILE}" <<'EOF'
---
title: 关于我
permalink: /about/
icon: fas fa-info-circle
order: 4
---

这里记录后端、基础架构、性能工程、数据库内核与 AI Agent 方向的学习和实践。

个人学习记录、简历、面试复盘与作者画像保存在独立的私有仓库中。
EOF
