# src/core/vcs/provider.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict

class VCSProvider(ABC):
    """
    Provider-agnostic interface for VCS operations needed by the self-heal PR flow.

    Implementations:
      - Bitbucket Cloud: src/core/vcs/bitbucket.py
      - GitHub:          src/core/vcs/github.py

    Contract:
      1) clone_repo() returns a filesystem path to a fresh clone of the target repo.
      2) create_branch() must create/switch to <branch> from <base> inside the clone.
      3) commit_and_push() stages all changes in the clone, commits, pushes, and
         returns the created commit SHA as a string.
      4) create_pull_request() opens a PR/MR and returns the provider's raw response
         as a dict (so callers can read platform-specific fields if needed).
    """

    @abstractmethod
    def clone_repo(self) -> str:
        """
        Clone the target repository and return the absolute path to the clone.
        Implementations should set the remote name to 'origin'.
        """
        raise NotImplementedError

    @abstractmethod
    def create_branch(self, clone_dir: str, branch: str, base: str) -> None:
        """
        Create/switch to 'branch' starting from 'base' (e.g., 'main') inside clone_dir.
        The branch should be created locally and checked out.
        """
        raise NotImplementedError

    @abstractmethod
    def commit_and_push(self, clone_dir: str, message: str, branch: str) -> str:
        """
        Stage all changes, create a commit with 'message', push to 'origin <branch>'.
        Returns the commit SHA of the created commit.
        """
        raise NotImplementedError

    @abstractmethod
    def create_pull_request(
        self,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str
    ) -> Dict:
        """
        Create a pull request from source_branch → target_branch with the given
        title/body and return the provider's response as a dictionary.
        """
        raise NotImplementedError