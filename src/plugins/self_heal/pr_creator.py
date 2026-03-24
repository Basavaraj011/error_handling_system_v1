# src/plugins/self_heal/pr_creator.py
from __future__ import annotations

import re
import time
import os
import subprocess
from typing import Dict, Any, List, Optional

from connections.vcs import get_provider
from .repo_ops import copy_changes
from .pr_template import PRContext, build_pr_title, build_pr_body
from database.database_operations import insert_pr_metadata
from src.plugins.jira_ticketing.notifier import send_teams_notification

CONFIDENCE_PR_MIN = 0.55
CONFIDENCE_DRAFT_MIN = 0.40
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9._\-]+")


def _sanitize(s: str) -> str:
    s = _SANITIZE_RE.sub("-", s).strip("-")
    return s or "auto-fix"


def open_pr(
    provider_kind: str,
    provider_opts: Dict[str, Any],
    engine_root: str,
    solution: Dict[str, Any],
    changed_files_rel: List[str],
    base_branch: str = "main",
    ticket_key: Optional[str] = None,
) -> Dict[str, Any]:

    if not changed_files_rel:
        raise ValueError("changed_files_rel cannot be empty.")

    provider = get_provider(provider_kind, **provider_opts)

    repo_dir = engine_root  # === NO CLONE ===

    # ------------------------------
    # 2. Create branch
    # ------------------------------
    prefix = f"{ticket_key}-" if ticket_key else ""
    branch = f"selfheal/{prefix}-{int(time.time())}"

    provider.create_branch(repo_dir, branch, base_branch)

    # ------------------------------
    # 3. Commit & push
    # ------------------------------
    commit_msg = (
        "Self-Heal: automated fix\n\n"
        "Files:\n" + "".join(f"- {p}\n" for p in changed_files_rel)
    )

    commit_sha = provider.commit_and_push(repo_dir, commit_msg, branch)

    # ------------------------------
    # 4. Build PR payload
    # ------------------------------
    ctx = PRContext(
        solution_summary=solution,
        ticket_key=ticket_key,
        file_list=changed_files_rel,
    )

    title = build_pr_title(ctx)
    body = build_pr_body(ctx, {"Commit": commit_sha, "Branch": branch})

    pr = provider.create_pull_request(title, body, branch, base_branch)

    print("********** PR: ", pr)

    if pr:
        pr_link = pr['links']['html']['href']
        summary = f"""
                    PR Description : {pr.get('description')}
                    PR Link : {pr_link}
                    """
        ticket_key = pr.get('id')
        send_teams_notification(ticket_key, summary, pr = True)

    # Metadata write (unchanged)
    try:
        insert_pr_metadata({
            "provider": provider_kind,
            "workspace_or_project": provider_opts.get("workspace") or provider_opts.get("owner"),
            "repo_slug": provider_opts.get("repo_slug") or provider_opts.get("repo"),
            "pr_id": pr.get("id") or pr.get("number"),
            "pr_url": pr.get("links", {}).get("html", {}).get("href", "") or pr.get("html_url", ""),
            "title": title,
            "branch": branch,
            "base_branch": base_branch,
            "commit_sha": commit_sha,
            "rca_short": ctx.rca_short,
            "rca_full": ctx.rca_full,
            "solution_summary": ctx.solution_summary,
            "rollback_steps": ctx.rollback_steps,
            "test_notes": ctx.test_notes,
        })
    except Exception:
        pass

    return pr