# src/plugins/chatbot/prompts.py
from __future__ import annotations
import os
import yaml
from functools import lru_cache
from typing import Dict, Any, Optional, Tuple

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
PROMPTS_PATH = os.path.join(workspace_root, "prompts", "chatbot", "prompts.yml")

class PromptResolver:
    def __init__(self, path: str = PROMPTS_PATH):
        self.path = path
        self._data = self._load()

    @lru_cache(maxsize=1)
    def _load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def reload(self) -> None:
        # if you want hot-reload in dev
        self._load.cache_clear()
        self._data = self._load()

    def get(self, prompt_type: str, team_key: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Returns: (template_text, gen_params)
        gen_params includes temperature/max_tokens defaults (and can be extended later).
        """
        data = self._data or {}
        defaults = data.get("defaults", {})
        temps = data.get("templates", {})
        overrides = data.get("overrides", {})

        # team override if present
        if team_key and team_key in overrides:
            t_over = overrides[team_key].get("templates", {})
            template = t_over.get(prompt_type) or temps.get(prompt_type)
        else:
            template = temps.get(prompt_type)

        if not template:
            # fall back to generic
            template = temps.get("generic", "Summarize the results.")

        gen_params = {
            "max_tokens": defaults.get("max_tokens", 350),
            "temperature": defaults.get("temperature", {}).get(prompt_type, 0.4)
        }
        return template, gen_params

    @staticmethod
    def render(template: str, **kwargs) -> str:
        # Very simple {name} formatting: the placeholders must match keys passed
        try:
            return template.format(**kwargs)
        except Exception:
            # Be forgiving if a placeholder is missing — best effort
            return template

# singleton style helper (optional)
_resolver: Optional[PromptResolver] = None

def get_resolver() -> PromptResolver:
    global _resolver
    if _resolver is None:
        _resolver = PromptResolver()
    return _resolver