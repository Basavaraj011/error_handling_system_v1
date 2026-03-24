# src/plugins/self_heal/repo_ops.py
from __future__ import annotations
import shutil
from pathlib import Path
from typing import Iterable, List

def copy_changes(engine_root: str, clone_root: str, rel_paths: Iterable[str]) -> List[str]:
    engine_root = Path(engine_root)
    clone_root = Path(clone_root)
    written = []
    for rel in rel_paths:
        src = (engine_root / rel).resolve()
        dst = (clone_root / rel).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(str(dst))
    return written