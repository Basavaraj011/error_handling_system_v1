# solution_generator_v2.py (updated)
import json
from html import unescape as _unescape
from connections.ai_connections import AIClient

class SolutionGenerator:
    def __init__(self):
        self.ai = AIClient()

    def _clean(self, s: str) -> str:
        return (s or "").strip("` \n\t")

    def generate_fix(
        self,
        original: str,
        error_stack_trace: str,
        prev_error: str = None,
        prev_solution: str = None,
        confidence: float = 0.8,
    ):
        """
        Generate a fix proposal using AI.
        - original: current file content (empty string for first call)
        - error_stack_trace: the current error traceback
        - prev_error: previous error message (if available)
        - prev_solution: previous solution text (if available)
        - confidence: confidence in reusing/adapting past solution
        """

        prompt = f"""
You are an expert software engineer.

REQUIREMENTS:
- Output STRICT JSON ONLY with keys: "file_path", "patch", "updated_file", "solution".
- If you return "patch", it MUST be a valid unified diff that `git apply` accepts:
  * Include headers exactly: `--- a/<path>` then `+++ b/<path>`
  * Each hunk MUST have numeric ranges: `@@ -<old_start>,<old_len> +<new_start>,<new_len> @@`
  * No code fences, no extra commentary, no ellipses placeholders.
- If you cannot produce a valid diff, leave "patch" empty and provide the FULL UPDATED FILE in "updated_file".

TASK:
1) Pick up all files mentioned in the stack trace.
2) Files and errors can be interdependent on other files in the repo.
3) Iterate through all the files in the repo and produce a fix wherever necessary based on the error.
4) Always try to figure out the errors from where it is originating and try to fix it.
5) Multiple files can be modified to fix the error.
6) Propose a fix as a unified diff against ORIGINAL FILE. Keep unrelated lines unchanged.
7) Provide a short human-readable "solution" (one or two sentences).
8) Please ensure the fix is syntactically correct.
9) Dont create any extra files.

Return STRICT JSON ONLY:
{{
  "file_path": "<like src/some.py>",
  "patch": "<unified diff or empty string>",
  "updated_file": "<full file only if patch empty>",
  "solution": "<short text>"
}}

ORIGINAL FILE:
{original}

TRACEBACK:
{error_stack_trace}

PREVIOUS_ERROR:
{prev_error or "None"}

PREVIOUS_SOLUTION:
{prev_solution or "None"}

PREVIOUS_SOLUTION_CONFIDENCE:
{confidence}
"""

        out = self.ai.generate_text(prompt)
        data = json.loads(self._clean(out))

        return {
            "file_path": data.get("file_path", "").strip(),
            "patch": data.get("patch", "").strip(),
            "updated_file": data.get("updated_file", "").strip(),
            "solution": data.get("solution", "").strip(),
        }