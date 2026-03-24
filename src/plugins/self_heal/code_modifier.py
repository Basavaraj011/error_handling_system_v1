import os
import re
import difflib
import subprocess
import tempfile
from html import unescape as _unescape
from typing import Optional, List, Dict

from src.plugins.self_heal.solution_generator import SolutionGenerator
from src.plugins.self_heal.learning import LearningEngine

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ================================================================
# PATCH UTILITIES (SMART + STRICT) — no validators anywhere
# ================================================================
SMART_DEFAULTS = {
    "max_offset": 12,            # search window up/down from expected anchor
    "ignore_ws": True,           # whitespace-insensitive context matching
    "normalize_eols": True,      # convert CRLF→LF prior to compare
    "min_anchor_score": 0.6,     # min ratio of matched context lines to accept anchor
    "require_edge_match": False, # require first & last context lines to match if present
}

def _normalize_eols(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")

def _cmp_line(a: str, b: str, ignore_ws: bool) -> bool:
    if ignore_ws:
        return " ".join(a.split()) == " ".join(b.split())
    return a == b

def _strip_fences(text: str) -> str:
    # Remove ```lang ... ``` fences if the LLM wrapped the diff
    return re.sub(r"\`\`\`(?:[\w+-]+)?\s*([\s\S]*?)\`\`\`", r"\1", text).strip() if text else text

def _normalize_headers(patch: str, file_path: str) -> str:
    """
    Ensure '--- a/<file>' and '+++ b/<file>' headers exist/are normalized,
    since LLMs sometimes omit or alter them.
    """
    out: List[str] = []
    old, new = False, False
    for line in patch.splitlines():
        if line.startswith("--- ") and not old:
            out.append(f"--- a/{file_path}")
            old = True
        elif line.startswith("+++ ") and not new:
            out.append(f"+++ b/{file_path}")
            new = True
        else:
            out.append(line)
    return "\n".join(out)

def _is_valid_diff(patch: str) -> bool:
    if not patch:
        return False
    p = _strip_fences(patch)
    lines = [l for l in p.splitlines() if l.strip()]
    if len(lines) < 3:
        return False
    if not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        return False
    return any(l.startswith("@@") for l in lines)

# ----- Strict (legacy) applier -----
def apply_patch_strict(original: str, patch: str) -> str:
    """
    Strict unified diff applier:
    - exact context line matches
    - no offset search
    - raises ValueError on mismatch
    """
    orig = original.splitlines(keepends=True)
    diff = patch.splitlines(keepends=True)
    out: List[str] = []
    i = 0  # index in diff
    o = 0  # index in original

    while i < len(diff):
        line = diff[i]
        if line.startswith(("---", "+++")):
            i += 1
            continue

        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
            if not m:
                raise ValueError(f"Invalid hunk header: {line!r}")
            old_start = int(m.group(1)) - 1

            # copy original up to hunk start
            while o < old_start:
                out.append(orig[o])
                o += 1

            i += 1
            # body
            while i < len(diff):
                pl = diff[i]
                if pl.startswith(("@@", "---", "+++")):
                    break
                if pl.startswith("-"):
                    o += 1
                elif pl.startswith("+"):
                    out.append(pl[1:])
                else:
                    if orig[o].rstrip("\n") != pl[1:].rstrip("\n"):
                        raise ValueError("Context mismatch (strict).")
                    out.append(orig[o])
                    o += 1
                i += 1
            continue

        i += 1

    out.extend(orig[o:])
    return "".join(out)

# ----- SMART (fuzzy) applier -----
class Hunk:
    def __init__(self, old_start: int, old_len: int, new_start: int, new_len: int, lines: List[str]):
        self.old_start = old_start
        self.old_len = old_len
        self.new_start = new_start
        self.new_len = new_len
        self.lines = lines  # includes ' ', '+', '-'

def _parse_unified_diff(patch: str) -> List['Hunk']:
    lines = patch.splitlines(keepends=True)
    hunks: List[Hunk] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("@@"):
            m = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", ln)
            if not m:
                raise ValueError(f"Invalid hunk header: {ln!r}")

            old_start = int(m.group(1)) - 1
            old_len = int(m.group(2) or 1)
            new_start = int(m.group(3)) - 1
            new_len = int(m.group(4) or 1)

            i += 1
            body: List[str] = []
            while i < len(lines):
                cur = lines[i]
                if cur.startswith(("@@", "---", "+++")):
                    break
                if cur and cur[0] in (" ", "+", "-") or cur == "\n":
                    body.append(cur)
                i += 1

            hunks.append(Hunk(old_start, old_len, new_start, new_len, body))
            continue
        i += 1
    return hunks

def _extract_context_lines(hunk: Hunk) -> List[str]:
    return [ln[1:] for ln in hunk.lines if ln.startswith(" ")]

def _score_anchor(orig: List[str], ctx: List[str], pos: int, opts: Dict) -> float:
    """
    Returns ratio [0..1] of matched context lines if applied at 'pos'
    """
    if not ctx:
        return 1.0
    match = 0
    ignore_ws = opts["ignore_ws"]
    for i, cl in enumerate(ctx):
        oi = pos + i
        if oi >= len(orig):
            break
        if _cmp_line(orig[oi].rstrip("\n"), cl.rstrip("\n"), ignore_ws):
            match += 1
    return match / max(1, len(ctx))

def _find_anchor(orig: List[str], expected_pos: int, ctx: List[str], opts: Dict) -> Optional[int]:
    """
    Search for best anchor within [expected_pos - max_offset, +max_offset]
    """
    max_off = opts["max_offset"]
    min_score = opts["min_anchor_score"]
    require_edge = opts["require_edge_match"]

    best_pos = None
    best_score = -1.0

    # Search window
    start = max(0, expected_pos - max_off)
    end = min(len(orig), expected_pos + max_off + 1)

    for pos in range(start, end):
        score = _score_anchor(orig, ctx, pos, opts)

        if require_edge and ctx:
            first_ok = _cmp_line(orig[pos].rstrip("\n"), ctx[0].rstrip("\n"), opts["ignore_ws"]) if pos < len(orig) else False
            last_ok = False
            if len(ctx) > 1 and (pos + len(ctx) - 1) < len(orig):
                last_ok = _cmp_line(
                    orig[pos + len(ctx) - 1].rstrip("\n"),
                    ctx[-1].rstrip("\n"),
                    opts["ignore_ws"],
                )
            if not (first_ok and (last_ok or len(ctx) == 1)):
                continue

        if score > best_score:
            best_score = score
            best_pos = pos

        if best_pos is not None and best_score >= min_score:
            return best_pos

    return None

def apply_patch_smart(original: str, patch: str, options: Optional[Dict] = None) -> str:
    """
    Smart (fuzzy) unified diff applier:
    - normalizes EOLs
    - whitespace-insensitive context matching (configurable)
    - offset search window around expected position
    - applies hunks at best anchor
    """
    opts = {**SMART_DEFAULTS, **(options or {})}
    orig_text = _normalize_eols(original) if opts["normalize_eols"] else original
    patch_text = _normalize_eols(patch) if opts["normalize_eols"] else patch

    orig = orig_text.splitlines(keepends=True)
    hunks = _parse_unified_diff(patch_text)

    out: List[str] = []
    cursor = 0  # pointer into 'orig'

    for h in hunks:
        ctx = _extract_context_lines(h)

        # try best anchor
        expected = h.old_start
        anchor = _find_anchor(orig, expected, ctx, opts)
        if anchor is None:
            raise ValueError("Smart anchor not found (context too different).")

        # copy up to anchor
        while cursor < anchor:
            out.append(orig[cursor])
            cursor += 1

        # apply hunk body relative to anchor
        o = anchor
        for ln in h.lines:
            if ln.startswith(" "):
                # must match: trust anchor scoring; still sanity-check len
                out.append(orig[o])
                o += 1
            elif ln.startswith("-"):
                # remove one original line
                o += 1
            elif ln.startswith("+"):
                out.append(ln[1:])
            else:
                # empty line in diff body (should be a ' ' context without marker)
                out.append(ln)

        # move main cursor to new original carry-over
        cursor = o

    # append tail
    out.extend(orig[cursor:])
    return "".join(out)


# ================================================================
# CodeModifier — aligned to your reference + run_self_heal usage
# ================================================================
class CodeModifier:
    """
    Matches the v2 reference flow (two-step LLM) while keeping
    the class name `CodeModifier` so run_self_heal.py can import it.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.sg = SolutionGenerator()
        self.learn = LearningEngine()

    # ------------------------------------
    # Helpers
    # ------------------------------------
    def _is_git_repo(self) -> bool:
        try:
            r = subprocess.run(
                ["git", "-C", self.repo_path, "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True
            )
            return r.returncode == 0 and "true" in r.stdout.lower()
        except Exception:
            return False

    def _apply_patch_git(self, file_path: str, patch: str) -> bool:
        if not self._is_git_repo():
            return False
        try:
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                tmp.write(patch if patch.endswith("\n") else patch + "\n")
                tmp_path = tmp.name

            cmd = ["git", "-C", self.repo_path, "apply", "--reject", "--whitespace=nowarn", tmp_path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            ok = (r.returncode == 0)
            if ok:
                logger.info("[CodeModifier] Applied via GIT")
            return ok
        except Exception:
            return False

    def _detect_lang(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".sql", ".tsql"):
            return "sql"
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cs": "csharp",
            ".go": "go",
        }.get(ext, "unknown")

    def _read(self, p: str) -> str:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def _write(self, p: str, content: str):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def _make_synthetic_patch(self, original: str, updated: str, file_path: str) -> str:
        return "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))

    # -------------------------------------------------------------
    # MAIN ENTRY (matches your reference interface)
    # -------------------------------------------------------------
    def apply_fix(
        self,
        repo_name: str,
        error_stack_trace: str,
        prev_error: Optional[str] = None,
        prev_solution: Optional[str] = None,
        confidence: float = 0.8,   # confidence in reusing past solution
    ):
        # 1) First LLM call: detect file path + draft patch
        logger.info("[CodeModifier] First LLM call to detect file path / produce patch")
        first = self.sg.generate_fix(
            original="",  # no file content yet
            error_stack_trace=error_stack_trace,
            prev_error=prev_error,
            prev_solution=prev_solution,
            confidence=confidence,
        )

        file_path = first["file_path"]
        if not file_path:
            raise ValueError("AI did not return a file_path. Cannot continue.")

        abs_path = os.path.join(self.repo_path, file_path)
        original = self._read(abs_path)
        lang = self._detect_lang(file_path)

        # 2) Second LLM call WITH actual file content
        logger.info("[CodeModifier] Second LLM call with file content for proper diff")
        result = self.sg.generate_fix(
            original=original,
            error_stack_trace=error_stack_trace,
            prev_error=prev_error,
            prev_solution=prev_solution,
            confidence=confidence,
        )

        patch = (result.get("patch") or "").strip()
        updated_full = (result.get("updated_file") or "").strip()
        solution_text = (result.get("solution") or "").strip()

        # Normalize/clean any fenced code blocks in patch and ensure headers
        if patch:
            patch = _normalize_headers(_strip_fences(_unescape(patch)), file_path)
            if not _is_valid_diff(patch):
                logger.debug("[CodeModifier] Patch not a valid unified diff; will use fallback if needed.")
        
        if (not patch or not _is_valid_diff(patch)) and updated_full and updated_full != original:
            patch = self._make_synthetic_patch(original, updated_full, file_path)


        # 3) Try applying patch
        updated = None
        applied = False

        if patch and self._apply_patch_git(file_path, patch):
            updated = self._read(abs_path)
            applied = True

        if not applied and patch:
            try:
                updated = apply_patch_smart(original, patch)
                applied = True
                logger.info("[CodeModifier] Applied via SMART applier")
            except Exception as e:
                logger.debug(f"[SMART] failed: {e}")

        if not applied and patch:
            try:
                updated = apply_patch_strict(original, patch)
                applied = True
                logger.info("[CodeModifier] Applied via STRICT applier")
            except Exception as e:
                logger.debug(f"[STRICT] failed: {e}")

        if not applied:
            updated = updated_full if updated_full else original
            logger.info("[CodeModifier] Applied via FULL-FILE fallback")

        # 4) Write back to file
        self._write(abs_path, updated)
        logger.info(f"[CodeModifier] Patch completed for {file_path}")

        # 5) Store learning result (no validators involved)
        self.learn.record_outcome(
            error_hash="auto",
            file_path=file_path,
            lang=lang,
            confidence=confidence,
            applied_patch=patch,
        )

        return {
            "file": file_path,
            "patch": patch,
            "patch_used": bool(patch),
            "solution": solution_text,
        }