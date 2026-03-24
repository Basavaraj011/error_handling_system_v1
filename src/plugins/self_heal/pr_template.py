# File: src/plugins/self_heal/pr_template.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class PRContext:
    solution_summary: str
    ticket_key: Optional[str] = None
    file_list: Optional[List[str]] = None


def build_pr_title(ctx: PRContext) -> str:
    """
    Example:
    [AUTO-FIX 92%] API-143 Null pointer in parseConfig
    """
    ticket = f"{ctx.ticket_key} " if ctx.ticket_key else ""

    return f"{ticket}"


def build_pr_body(ctx: PRContext, extra_meta: Optional[Dict] = None) -> str:
    """
    Builds a standardized PR markdown body containing:
    - RCA
    - Solution
    - Rollback steps
    - Test notes
    - Changed files
    - Metadata (confidence, commit, etc.)
    """

    # changed files section
    file_section = (
        "".join(f"- `{f}`\n" for f in (ctx.file_list or []))
        if ctx.file_list else "- (See PR diff)"
    )

    # metadata
    meta_lines = ""
    if extra_meta:
        for key, value in extra_meta.items():
            meta_lines += f"- **{key}**: {value}\n"

    return f"""
---

## 🛠️ Solution Summary
{ctx.solution_summary}

---

## 📂 Changed Files
{file_section}

---
""".strip()