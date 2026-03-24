"""
Unified AI client wrapper supporting multiple providers (Claude, OpenAI, etc)
"""
from typing import Optional, Dict, Any, List, Tuple
from config.settings import (
    AI_PROVIDER, AI_MODEL, AI_API_KEY,
    AZ_END_POINT, AZ_AI_API_KEY,
    SERVICE_LINE, BRAND, PROJECT
)
import logging
import os
import json
import time
import random

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """Structured AI client error with optional HTTP and provider metadata."""
    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None,
                 request_id: Optional[str] = None, provider: Optional[str] = None,
                 extra: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id
        self.provider = provider
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "status": self.status,
            "code": self.code,
            "request_id": self.request_id,
            "provider": self.provider,
            "extra": self.extra,
        }


class AIClient:
    """Unified interface for multiple AI providers"""

    def __init__(self, provider: str = AI_PROVIDER, model: str = AI_MODEL, api_key: str = AI_API_KEY):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.client = None
        self._initialize_client()

        # ---- APIM / Azure settings ----
        self.apim_url = AZ_END_POINT
        self.apim_sub_key = AZ_AI_API_KEY
        # If APIM forwards api-key to Azure backend, reuse same key by default
        self.apim_forward_api_key = AZ_AI_API_KEY

        # ---- Resilience / timeouts (can be overridden by env) ----
        self.max_retries = int(os.getenv("AI_MAX_RETRIES", "4"))
        self.initial_backoff_s = float(os.getenv("AI_INITIAL_BACKOFF_S", "0.6"))
        self.max_backoff_s = float(os.getenv("AI_MAX_BACKOFF_S", "6.0"))
        self.timeout_s = float(os.getenv("AI_TIMEOUT_S", "30.0"))

        # Keep last structured error for diagnostics
        self._last_error: Optional[AIClientError] = None

    def _initialize_client(self) -> None:
        """Initialize the appropriate AI client based on provider"""
        try:
            if self.provider == "anthropic":
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)

            elif self.provider == "openai":
                # Legacy OpenAI (0.x) ChatCompletion path
                import openai  # type: ignore
                openai.api_key = self.api_key
                self.client = openai

            elif self.provider == "azure_apim_chat":
                # Lazily created per-call with AzureOpenAI; no persistent client needed here.
                pass

            logger.info(f"Initialized AI client: {self.provider}")
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")

    # ---------------- Utilities ----------------

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Extract content inside ``` blocks if present; else return trimmed text."""
        if not text:
            return text
        import re
        pat = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
        m = pat.search(text)
        if m:
            return m.group(1).strip()
        return text.strip()

    def last_error_info(self) -> Optional[Dict[str, Any]]:
        return self._last_error.to_dict() if self._last_error else None

    # --------------- Robust HTTP retry wrapper ---------------

    def _request_with_retry(self, fn, *args, **kwargs):
        """
        Retry wrapper for provider calls (rate-limit 429, 5xx, timeouts).
        Exponential backoff with jitter.
        """
        attempt = 0
        backoff = self.initial_backoff_s

        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                attempt += 1
                # Extract some structured info if available
                status, code, req_id = self._extract_error_parts(e)
                retriable = status in (429, 500, 502, 503, 504) or "timeout" in str(e).lower()

                if attempt > self.max_retries or not retriable:
                    self._last_error = AIClientError(
                        message=f"AI request failed after {attempt} attempt(s): {e}",
                        status=status, code=code, request_id=req_id,
                        provider=self.provider, extra={"exception_type": type(e).__name__}
                    )
                    logger.error(f"[AI] Fatal error: {self._last_error.to_dict()}")
                    raise

                sleep_for = min(self.max_backoff_s, backoff * (1.5 + random.random()))
                logger.warning(f"[AI] Retrying (attempt {attempt}/{self.max_retries}) in {sleep_for:.2f}s "
                               f"due to status={status} code={code} err={e}")
                time.sleep(sleep_for)
                backoff = sleep_for  # exponential-ish with jitter

    @staticmethod
    def _extract_error_parts(e: Exception) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """
        Best-effort extraction of HTTP status, error code, and request id from provider exceptions.
        """
        status = None
        code = None
        request_id = None

        # Azure/OpenAI python SDK exceptions often have .status_code / .response
        if hasattr(e, "status_code"):
            status = getattr(e, "status_code")
        if hasattr(e, "code"):
            code = getattr(e, "code")
        # Azure SDK sometimes embeds details in e.args or e.response
        if hasattr(e, "response"):
            try:
                resp = e.response  # type: ignore
                if isinstance(resp, dict):
                    status = status or resp.get("status")
                    code = code or resp.get("error", {}).get("code")
                    request_id = resp.get("request_id") or resp.get("x-request-id")
            except Exception:
                pass

        # Fallback: probe string for common fields
        s = str(e)
        if "request id" in s.lower():
            # not perfect, but might be useful to surface something
            request_id = request_id or s

        return status, code, request_id

    # ---------------- APIM Chat Completions (Azure) ----------------

    def _call_apim_chat_completions(self, prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
        """
        Calls APIM Chat Completions endpoint with correct content-part format.
        Returns plain text (model's message.content).
        """
        if not AZ_END_POINT or not AZ_AI_API_KEY:
            logger.error("AZ_END_POINT or AZ_AI_API_KEY is missing in settings.")
            return None

        from openai import AzureOpenAI  # type: ignore

        DEPLOYMENT = self.model
        END_POINT = AZ_END_POINT
        OPENAI_API_KEY = AZ_AI_API_KEY
        OPENAI_API_VERSION = '2024-10-21'

        # Default headers; APIM may inspect these
        headers = {
            'x-service-line': SERVICE_LINE,
            'x-brand': BRAND,
            'x-project': PROJECT,
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'Ocp-Apim-Subscription-Key': OPENAI_API_KEY,
            'api-version': 'v15'
        }
        # If APIM is configured to forward api-key to Azure backend
        if self.apim_forward_api_key:
            headers["api-key"] = self.apim_forward_api_key

        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=END_POINT,
            api_key=OPENAI_API_KEY,
            azure_deployment=DEPLOYMENT,
            default_headers=headers,
            timeout=self.timeout_s
        )

        # ✅ Correct content-part message format
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        def _do_call():
            return client.chat.completions.create(
                model=DEPLOYMENT,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        try:
            resp = self._request_with_retry(_do_call)
            # Azure SDK returns typed object; content can be str or list-of-parts
            content = resp.choices[0].message.content
            if isinstance(content, list):
                out = ""
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        out += part.get("text", "")
                return self._strip_code_fences(out.strip())
            return self._strip_code_fences(str(content).strip())
        except Exception as e:
            self._last_error = AIClientError(
                message=f"APIM chat call failed: {e}",
                provider="azure_apim_chat",
                extra={"prompt_len": len(prompt), "temperature": temperature, "max_tokens": max_tokens}
            )
            logger.error(f"APIM chat call failed: {self._last_error.to_dict()}")
            return None

    # ---------------- existing API, now routes to provider ----------------

    def generate_text(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.1) -> Optional[str]:
        """
        Generate text using the configured AI provider.
        Returns normalized plain text, or None on failure.
        """
        try:
            if self.provider == "anthropic":
                import anthropic  # type: ignore
                # Claude v2+ API requires content as list with text blocks
                resp = self._request_with_retry(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]
                )
                # Claude response: content is a list of blocks
                parts = getattr(resp, "content", [])
                text_out = ""
                for p in parts:
                    if getattr(p, "type", None) == "text":
                        text_out += getattr(p, "text", "")
                return self._strip_code_fences(text_out)

            elif self.provider == "openai":
                # Legacy OpenAI 0.x call
                response = self._request_with_retry(
                    self.client.ChatCompletion.create,
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout_s
                )
                return self._strip_code_fences(response.choices[0].message.content)

            elif self.provider == "azure_apim_chat":
                # APIM → Azure OpenAI chat completions
                return self._call_apim_chat_completions(prompt, max_tokens, temperature)

            else:
                self._last_error = AIClientError(f"Unsupported provider: {self.provider}")
                logger.error(self._last_error)
                return None

        except AIClientError:
            # already logged and structured
            return None
        except Exception as e:
            self._last_error = AIClientError(
                message=f"Failed to generate text: {e}", provider=self.provider
            )
            logger.error(f"Failed to generate text: {self._last_error.to_dict()}")
            return None

    # ---------------- Convenience helpers for your existing utilities ----------------

    def analyze_error(self, error_message: str, context: str = "") -> Optional[str]:
        """Analyze an error and provide insights"""
        prompt = f"""Analyze the following error and provide insights:

        Error:
        {error_message}

        Context:
        {context}

        Please provide:
        1) Root cause analysis
        2) Suggested solutions
        3) Prevention measures
        """
        return self.generate_text(prompt)

    def generate_solution(self, problem: str, codebase_context: str = "") -> Optional[str]:
        """Generate a solution for a problem"""
        prompt = f"""Generate a solution for the following problem:

        Problem:
        {problem}

        Codebase Context:
        {codebase_context}

        Please provide:
        1) Detailed solution approach
        2) Code changes required
        3) Testing recommendations
        """
        return self.generate_text(prompt)