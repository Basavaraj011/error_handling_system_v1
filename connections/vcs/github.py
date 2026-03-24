# src/core/vcs/github.py
from __future__ import annotations
import subprocess, tempfile
from typing import Dict
import requests
from .provider import VCSProvider

class GitHubProvider(VCSProvider):
    """
    GitHub implementation.
    - Git clone over HTTPS with x-access-token:{token}@github.com
    - Create PR: POST https://api.github.com/repos/{owner}/{repo}/pulls
    """

    def __init__(self, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.base_url = "https://api.github.com"

    def _run(self, *args: str, cwd: str | None = None) -> str:
        return subprocess.check_output(args, cwd=cwd, text=True).strip()

    def clone_repo(self) -> str:
        clone_dir = tempfile.mkdtemp(prefix="selfheal_gh_")
        clone_url = f"https://x-access-token:{self.token}@github.com/{self.owner}/{self.repo}.git"
        self._run("git", "clone", "--origin", "origin", clone_url, clone_dir)
        return clone_dir

    def create_branch(self, clone_dir: str, branch: str, base: str) -> None:
        self._run("git", "fetch", "origin", base, cwd=clone_dir)
        self._run("git", "checkout", "-B", branch, f"origin/{base}", cwd=clone_dir)

    def commit_and_push(self, clone_dir: str, message: str, branch: str) -> str:
        self._run("git", "add", "-A", cwd=clone_dir)
        self._run("git", "-c", "user.name=SelfHeal Bot", "-c", "user.email=bot@local",
                  "commit", "-m", message, cwd=clone_dir)
        sha = self._run("git", "rev-parse", "HEAD", cwd=clone_dir)
        self._run("git", "push", "-u", "origin", branch, cwd=clone_dir)
        return sha

    def create_pull_request(self, title: str, body: str, source_branch: str, target_branch: str) -> Dict:
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls"
        payload = {"title": title, "head": source_branch, "base": target_branch, "body": body}
        r = requests.post(url, json=payload, headers={
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        })
        r.raise_for_status()
        return r.json()