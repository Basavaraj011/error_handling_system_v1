# src/plugins/chatbot/query_executor.py
"""
Query Executor - Handles intent mapping, SQL execution, and AI fallback for unmapped intents
(Updated for dynamic schema + new table structures + team->project_id via teams.yml)
"""

import re
import yaml
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path

from .prompts import get_resolver
from .query_catalog import QUERY_CATALOG
from .cards import count_card, list_card, kv_card
from .time_utils import (
    today_start_utc, yesterday_bounds_utc,
    this_week_start_utc, last_week_bounds_utc,
    this_month_start_utc, last_month_bounds_utc
)

# Use your Adaptive Cards for row tables & code blocks
# (scripts/ is on sys.path in your runners/webhook)
from scripts.adaptive_cards import table_card, code_block_card


# ----------------------------- CONFIG & TOKENS -----------------------------

# Align severity to uppercase to match typical stored values (e.g., HIGH)
SEVERITY_MAP = {
    "critical": "CRITICAL", "p0": "CRITICAL",
    "high": "HIGH", "p1": "HIGH",
    "medium": "MEDIUM", "med": "MEDIUM", "p2": "MEDIUM",
    "low": "LOW", "p3": "LOW",
}


class QueryExecutor:
    """
    Executes user queries against SQL Server with intent mapping.
    Falls back to AI-generated SQL if intent is not mapped.
    """
    GUIDANCE_MESSAGE = (
    "I couldn’t understand the question.\n\n"
    "Please include:\n"
    "• a status keyword (error, fail, incident, etc.)\n"
    "• the team/project ID (e.g., team_a, project_1)\n"
    "• a time period (today, yesterday, last 24 hours, this week)\n\n"
    "Example:\n"
    "“Show errors for team_a in the last 24 hours”"
    )

    # Token lists for flexible matching (handle typos, variants)
    # Add after existing failure tokens
    STATUS_TOKENS = [
        'fail', 'fial', 'failure', 'failures', 'fails', 'error', 'errors', 'incident', 'incidents',
        'success', 'succeeded', 'successful', 'passed', 'pass', 'ok', 'completed', 'complete',
        'build success', 'deploy success'
    ]

    JOB_TOKENS = [
        'ingestion','ingest','publishing','publish','publisher',
        'job','jobs','pipeline','status','health','product health',
        'running','run','currently running','long running','stuck','duration'
    ]

    TEAM_TOKENS = ['team', 'tame', 'teem', 'teaam', 'grup', 'group']
    PROJECT_TOKENS = ['project', 'proj', 'app', 'service']  # optional helpers
    REPO_TOKENS = ['repo', 'repository', 'codebase']

    # All-teams phrases
    ALL_TEAMS_TOKENS = [
        'all teams', 'across teams', 'for all teams', 'every team', 'each team',
        'per team', 'by team', 'teams overall', 'team-wise', 'teamwise'
    ]

    # List / details / display intent tokens (includes "what", guarded below)
    LIST_TOKENS = [
        'show', 'list', 'display', 'give me', 'fetch', 'get me', 'see',
        'actual', 'details', 'detail', 'full', 'full list',
        'what'
    ]

    # Period keyword sets
    PERIOD_TOKENS = {
        'fixed_yesterday': [
            'yesterday', 'yday', 'yestday', 'yesterda', 'yesterdy', 'ystrday',
            'yesturday', 'yestarday', 'yestaday',
            'last day', 'lastday', 'prev day', 'previous day', 'previus day'
        ],
        'fixed_today': [
            'today', 'tday', 'todai', 'todaya', 'todsy', 'todqy', 'todau', '2day'
        ],
        'fixed_last_24h': [
            'last 24 hours', 'last 24 hour', 'last24hours', 'last24',
            'past 24 hours', 'past24hours',
            '24 hours', '24 hour', '24hrs', '24hr', '24 h', '24h', '24',
            'last twenty four hours'
        ],
        'fixed_this_week': [
            'this week', 'thisweek', 'current week', 'curr week',
            'cur week', 'this wk', 'thiswk'
        ],
        'fixed_last_week': [
            'last week', 'lastweek', 'previous week', 'prev week',
            'previus week', 'last wk', 'lastwk'
        ],
        'fixed_this_month': [
            'this month', 'thismonth', 'current month', 'curr month',
            'cur month', 'this mnth', 'this mn'
        ],
        'fixed_last_month': [
            'last month', 'lastmonth', 'previous month', 'prev month',
            'previus month', 'last mnth', 'last mn'
        ],
        'fixed_last_2h': [
            'last 2 hours', 'last2hours', 'last 2 hour',
            'past 2 hours', 'past2hours', '2h', '2hr', '2hrs'
        ]
    }

    # --- AI escalation tokens (configurable via project_cfg['ai_routing']) ---
    RATIO_TOKENS = [
        '%', 'percent', 'percentage', 'ratio', 'share', 'proportion',
        'contribution', 'contribute', 'what fraction', 'fraction',
        'what portion', 'portion', 'relative', 'relative to'
    ]
    WHY_TOKENS = ['why', 'root cause', 'rca', 'cause of', 'cause', 'reason']
    COMPARE_TOKENS = [
        'compare', 'compared to', 'versus', 'vs', 'relative to',
        'delta', 'increase', 'decrease', 'change', 'trend vs'
    ]
    STATS_TOKENS = [
        'average', 'avg', 'mean', 'median', 'percentile', 'p95', 'p90', 'p99',
        'stddev', 'standard deviation', 'variance', 'distribution',
        'histogram', 'rate', 'per minute', 'per hour', 'per day'
    ]
    DISTINCT_TOKENS = ['unique', 'distinct', 'dedup', 'de-dup', 'per exception', 'per error type', 'by hash']
    JIRA_TOKENS = ['jira', 'ticket', 'tickets', 'issue', 'issues']
    JOIN_HINT_TOKENS = ['linked', 'associated', 'related', 'join', 'joined']

    def __init__(self, services: Dict[str, Any], project_cfg: Dict[str, Any]):
        """
        Args:
            services: Dict with 'db' (database connection), 'ai' (AI client), etc
            project_cfg: Project configuration
        """
        self.db = services["db"]
        self.ai = services.get("ai")
        self.project_cfg = project_cfg

        # Dynamic SQL schema (default to 'project_1')
        self.sql_schema = project_cfg.get("sql_schema")
        self.sql_database = project_cfg.get("sql_database")
        self.schema_qual = f"{self.sql_database}.{self.sql_schema}"

        print(f"✓ Using SQL schema: {self.sql_schema}")

        # Load team aliases (and optional repo aliases) from YAML
        ROOT = Path(__file__).resolve().parent.parent.parent.parent
        teams_file = ROOT / "config" / "teams.yml"
        with open(teams_file, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        self.teams_alias = (cfg.get("teams") or {})
        self.repo_alias = (cfg.get("repo_names") or {})  # optional

        print(f"✓ Loaded teams: {list(self.teams_alias.keys())}")
        print(f"✓ Loaded repos: {list(self.repo_alias.keys())}")

        # Vector defaults
        self.vector_top_k = 5
        self.vector_min_score = 0.80

    # ======================= PUBLIC API =======================

    def _wants_sql(self, text: str) -> bool:
        """Return True if the user asked to see the SQL/query."""
        tl = (text or "").lower()
        return any(pat in tl for pat in [
            "show sql", "what sql", "which sql", "return sql", "sql please",
            "show the query", "return the query", "query please"
        ]) or (("sql" in tl or "query" in tl) and any(k in tl for k in ["show", "what", "which", "return"]))

    def execute_user_query(self, user_text: str) -> Dict[str, Any]:
        """Main entry point: Execute a user query."""
        text = (user_text or "").strip().lower()

        # 👋 Health/smalltalk short-circuit
        if text in ("ping", "hi", "hello", "are you there?", "hey"):
            return {"type": "text", "content": "pong" if text == "ping" else "👋 I'm here."}

        wants_sql = self._wants_sql(text)

        # Extract team (single source of truth) and derive canonical project_id from YAML
        team_key = self._extract_team_key(text)
        canonical_project_id = None
        if team_key:
            entry = self.teams_alias.get(team_key, {})
            canonical_project_id = (entry or {}).get("project_id")

        # Optional repository extraction (only if you will introduce repo-aware QIDs)
        repo_name = self._extract_repo_name(text)

        severity = self._extract_severity(text)
        n_days = self._extract_n_days(text)
        ticket_id = self._extract_ticket_id(text)
        type_like = self._extract_exception_like(text)
        start_ts, end_ts = self._extract_date_range(text)
        period_id = self._extract_period_id(text)

        # DEBUG
        print("[EXTRACTION]")
        print(f"  team_key (alias):      {team_key}")
        print(f"  canonical_project_id:  {canonical_project_id}")
        print(f"  repo_name:             {repo_name}")
        print(f"  period_id:             {period_id}")
        print(f"  severity:              {severity}")
        print(f"  n_days:                {n_days}")

        # Try to match to a mapped intent (token-based)
        intent = self._match_intent_by_tokens(
            text, canonical_project_id, period_id, severity, n_days, ticket_id, start_ts, end_ts
        )
        print("\n[INTENT MATCH]")
        print(f"  intent: {intent}")

        if intent:
            # MAPPED INTENT: Use predefined SQL query
            return self._execute_mapped_intent(
                user_text=user_text, intent=intent, project_id=canonical_project_id,
                severity=severity, n_days=n_days, ticket_id=ticket_id,
                type_like=type_like, start_ts=start_ts, end_ts=end_ts, repo_name=repo_name,
                wants_sql=wants_sql
            )
        else:
            # UNMAPPED INTENT: Use AI to generate SQL and execute it
            ai_ctx = {
                "user_text": user_text,
                "project_id": canonical_project_id,
                "severity": severity,
                "n_days": n_days,
                "ticket_id": ticket_id,
                "type_like": type_like,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_id": period_id,
                "wants_sql": wants_sql
            }
            result = self._execute_ai_fallback(ai_ctx)
            
            if not result:
                return {"type": "text", "content": self.GUIDANCE_MESSAGE}
            if isinstance(result, dict) and result.get("type") == "text" and str(result.get("content", "")).strip().lower() in ("ok", "okay"):
                return {"type": "text", "content": self.GUIDANCE_MESSAGE}

            return result


    # ======================= TOKEN-BASED INTENT MATCHING =======================

    def _contains_any(self, text: str, token_list: List[str]) -> bool:
        """Check if text contains any token from the list"""
        t = (text or "").lower()
        return any(tok.lower() in t for tok in token_list)

    def _cfg_ai(self) -> Dict[str, Any]:
        """Convenience accessor for AI routing config with sensible defaults."""
        return {
            **{
                "enable_ratio": True,
                "enable_why": True,
                "enable_stats": True,
                "enable_compare": True,
                "enable_distinct": True,
                "cross_team_list_to_ai": True,
            },
            **(self.project_cfg.get("ai_routing", {}) if isinstance(self.project_cfg, dict) else {})
        }

    def _should_route_to_ai(self, text_l: str, project_id: Optional[str]) -> bool:
        """Return True if the question is better handled by AI (not in catalog)."""
        cfg = self._cfg_ai()

        # Percentage / share / ratio
        if cfg.get("enable_ratio") and self._contains_any(text_l, self.RATIO_TOKENS):
            return True
        # Why / RCA / explanatory
        if cfg.get("enable_why") and self._contains_any(text_l, self.WHY_TOKENS):
            return True
        # Stats / distribution / percentiles
        if cfg.get("enable_stats") and self._contains_any(text_l, self.STATS_TOKENS):
            return True
        # Comparisons / deltas
        if cfg.get("enable_compare") and self._contains_any(text_l, self.COMPARE_TOKENS):
            return True
        # Distinct/unique-style requests
        if cfg.get("enable_distinct") and self._contains_any(text_l, self.DISTINCT_TOKENS):
            return True
        # Cross-domain join-y asks: tickets + failures + linking hints
        has_jira = self._contains_any(text_l, self.JIRA_TOKENS)
        has_failure_context = self._contains_any(text_l, self.STATUS_TOKENS)
        has_join_hint = self._contains_any(text_l, self.JOIN_HINT_TOKENS)
        if has_jira and has_failure_context and has_join_hint:
            return True

        # Cross-team list without project context → AI fallback to avoid unbounded lists
        is_all_teams = any(tok in text_l for tok in self.ALL_TEAMS_TOKENS)
        wants_list = self._contains_any(text_l, self.LIST_TOKENS)
        if cfg.get("cross_team_list_to_ai") and wants_list and is_all_teams and not project_id:
            return True

        return False

    def _match_intent_by_tokens(
        self,
        text: str, project_id: Optional[str], period_id: Optional[str],
        severity: Optional[str], n_days: Optional[str], ticket_id: Optional[str],
        start_ts: Optional[datetime], end_ts: Optional[datetime]
    ) -> Optional[Dict[str, Any]]:
        """
        Token-based intent matcher.

        Priority:
        1) JOB-STATUS domain (ingestion/publishing/status/health/running/long-running)
            → route to job_status QIDs FIRST.
        2) Existing LIST and COUNT flows for error_logs (kept as-is below).
        """
        text_l = (text or "").lower()
        job_type = self._extract_job_type(text_l)
        # Gate: treat job tokens as status too (so we prefer job_status when present)
        has_status = self._contains_any(text_l, self.STATUS_TOKENS) or self._contains_any(text_l, self.JOB_TOKENS)
        if not has_status:
            return None

        # --- EARLY OVERRIDE: User wants ERROR DETAILS, not job_status ---

        DETAIL_TOKENS = ["explain", "why", "reason", "root cause", "details", "what happened"]

        wants_error_details = (
            self._contains_any(text_l, DETAIL_TOKENS)
            and self._contains_any(text_l, self.STATUS_TOKENS)
            and job_type is not None
        )

        if wants_error_details:
            # Route to ERROR_LOGS LIST for the correct period
            if period_id == "fixed_today":
                return {"id": "Q_ERRORS_TODAY_LIST", "query_id": "Q_ERRORS_TODAY_LIST"}

            if period_id == "fixed_last_24h":
                return {"id": "Q_ERRORS_LAST_24H_LIST", "query_id": "Q_ERRORS_LAST_24H_LIST"}

            if period_id == "fixed_yesterday":
                return {"id": "Q_ERRORS_YESTERDAY_LIST", "query_id": "Q_ERRORS_YESTERDAY_LIST"}

            # Default fallback → list all recent errors for that job's project
            return {"id": "Q_LIST_ALL_ERRORS", "query_id": "Q_LIST_ALL_ERRORS"}

        # ---------- JOB-STATUS PRIORITY BLOCK ----------

        wants_health = ("health" in text_l) or ("product health" in text_l)
        wants_status = ("status" in text_l) or ("how many" in text_l) or self._contains_any(text_l, self.JOB_TOKENS)

        if wants_status:
            # (A) Product health across all job types → job_status summary
            if wants_health:
                # Period mapping for health
                if self._contains_any(text_l, self.PERIOD_TOKENS.get('fixed_last_24h', [])) or "last 24" in text_l:
                    return {"id": "Q_PRODUCT_HEALTH_LAST_24H", "query_id": "Q_PRODUCT_HEALTH_LAST_24H"} 
                return {"id": "Q_PRODUCT_HEALTH_TODAY", "query_id": "Q_PRODUCT_HEALTH_TODAY"} 
            
            # --- PRODUCT HEALTH WITH CUSTOM DATE RANGE ---
        # --- PRODUCT HEALTH EXCLUSIVE ROUTING ---
            if "product" in text_l:
                # 1. custom date range
                if start_ts and end_ts:
                    return {
                        "id": "Q_PRODUCT_HEALTH_BY_DATE_RANGE",
                        "query_id": "Q_PRODUCT_HEALTH_BY_DATE_RANGE"
                    }

                # 2. today
                if "today" in text_l or period_id == "fixed_today":
                    return {
                        "id": "Q_PRODUCT_HEALTH_TODAY",
                        "query_id": "Q_PRODUCT_HEALTH_TODAY"
                    }

                # 3. last 24h
                if "24" in text_l or period_id == "fixed_last_24h":
                    return {
                        "id": "Q_PRODUCT_HEALTH_LAST_24H",
                        "query_id": "Q_PRODUCT_HEALTH_LAST_24H"
                    }

                # 4. fallback: today
                return {
                    "id": "Q_PRODUCT_HEALTH_TODAY",
                    "query_id": "Q_PRODUCT_HEALTH_TODAY"
                }


            # (B) Specific job type (ingestion/publishing) status/metrics
            if job_type:
                # Long-running jobs (e.g., "long running 24h", "stuck")
                if ("long running" in text_l) or ("stuck" in text_l):
                    return {"id": "Q_JOB_TYPE_LONG_RUNNING", "query_id": "Q_JOB_TYPE_LONG_RUNNING"}  # needs @job_type, @min_hours  [2] 

                # Running now/currently (e.g., "running now", "currently running")
                if ("running now" in text_l) or ("currently running" in text_l) or ("running currently" in text_l) or ("running" in text_l and "now" in text_l):
                    return {"id": "Q_JOB_TYPE_RUNNING_NOW", "query_id": "Q_JOB_TYPE_RUNNING_NOW"}  # needs @job_type  [2] 

                # Failures phrasing → counts from job_status
                if "fail" in text_l or "failed" in text_l or "failures" in text_l:
                    if self._contains_any(text_l, self.PERIOD_TOKENS.get('fixed_today', [])) or "today" in text_l:
                        return {"id": "Q_JOB_TYPE_FAILURES_TODAY", "query_id": "Q_JOB_TYPE_FAILURES_TODAY"}  # @job_type, @start_ts  [2] 
                    n_days_val = self._extract_n_days(text_l)
                    if n_days_val:
                        return {"id": "Q_JOB_TYPE_FAILURES_LAST_N_DAYS", "query_id": "Q_JOB_TYPE_FAILURES_LAST_N_DAYS"}  # @job_type, @n_days  [2] 
                    # If no explicit period, use "last N days" flavor (executor will pass n_days if extracted)
                    return {"id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS", "query_id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS"}  # [2] 

                # Generic “status of <job_type> …”
                if self._contains_any(text_l, self.PERIOD_TOKENS.get('fixed_today', [])) or "today" in text_l:
                    return {"id": "Q_JOB_TYPE_STATUS_TODAY", "query_id": "Q_JOB_TYPE_STATUS_TODAY"}  # @job_type, @start_ts  [2] 
                n_days_val = self._extract_n_days(text_l)
                if n_days_val:
                    return {"id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS", "query_id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS"}  # @job_type, @n_days  [2] 
                # Default: also use the last-N-days status form (commonly understood)
                return {"id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS", "query_id": "Q_JOB_TYPE_STATUS_LAST_N_DAYS"}  # [2] 

        # ---------- EXISTING LIST/COUNT LOGIC FOR error_logs (unchanged) ----------
        # AI escalation for special analytics
        if self._should_route_to_ai(text_l, project_id):
            return None  # forces execute_user_query to use AI fallback  [1]( )

        # LIST intent first (your prior behavior)
        wants_list = self._contains_any(text_l, self.LIST_TOKENS)
        if wants_list and "what" in text_l and not self._contains_any(text_l, self.STATUS_TOKENS):
            wants_list = False
        if wants_list:
            has_project_word_for_list = (project_id is not None) or self._contains_any(text_l, (self.TEAM_TOKENS + self.PROJECT_TOKENS))
            if not has_project_word_for_list:
                return None  # AI fallback

            # time-aware list QIDs for error logs  [1]( )
            for period_id_key, period_tokens in self.PERIOD_TOKENS.items():
                if self._contains_any(text_l, period_tokens):
                    if period_id_key == 'fixed_today':
                        return {"id": "Q_ERRORS_TODAY_LIST", "query_id": "Q_ERRORS_TODAY_LIST"}
                    if period_id_key == 'fixed_last_24h':
                        return {"id": "Q_ERRORS_LAST_24H_LIST", "query_id": "Q_ERRORS_LAST_24H_LIST"}
                    if period_id_key == 'fixed_yesterday':
                        return {"id": "Q_ERRORS_YESTERDAY_LIST", "query_id": "Q_ERRORS_YESTERDAY_LIST"}
                    break
            return {"id": "Q_LIST_ALL_ERRORS", "query_id": "Q_LIST_ALL_ERRORS"}

        # COUNT intent (error logs)
        is_all_teams = any(tok in text_l for tok in self.ALL_TEAMS_TOKENS)
        has_project_word = is_all_teams or project_id is not None or self._contains_any(text_l, (self.TEAM_TOKENS + self.PROJECT_TOKENS))
        if not has_project_word:
            return None

        # error count period mapping (all teams vs by-team)
        for period_id_key, period_tokens in self.PERIOD_TOKENS.items():
            if self._contains_any(text_l, period_tokens):
                if is_all_teams:
                    intent_id = self._period_to_intent_id_all_teams(period_id_key)
                else:
                    intent_id = self._period_to_intent_id(period_id_key)
                return {"id": intent_id, "query_id": intent_id}

        # No explicit period → fallback
        if is_all_teams:
            intent_id = 'Q_ERR_COUNT_ALL_TIME_ALL_TEAMS'
        else:
            intent_id = 'Q_ERR_COUNT_ALL_TIME_BY_TEAM'
        return {"id": intent_id, "query_id": intent_id}

    def _period_to_intent_id(self, period_id: str) -> str:
        period_intent_map = {
            'fixed_yesterday': 'Q_ERR_COUNT_YESTERDAY_BY_TEAM',
            'fixed_today': 'Q_ERR_COUNT_TODAY_BY_TEAM',
            'fixed_last_24h': 'Q_ERR_COUNT_LAST_24H_BY_TEAM',
            'fixed_this_week': 'Q_ERR_COUNT_THIS_WEEK_BY_TEAM',
            'fixed_last_week': 'Q_ERR_COUNT_LAST_WEEK_BY_TEAM',
            'fixed_this_month': 'Q_ERR_COUNT_THIS_MONTH_BY_TEAM',
            'fixed_last_month': 'Q_ERR_COUNT_LAST_MONTH_BY_TEAM',
            'fixed_last_2h': 'Q_ERR_COUNT_LAST_2H',
        }
        return period_intent_map.get(period_id, 'Q_ERR_COUNT_ALL_TIME_BY_TEAM')

    def _period_to_intent_id_all_teams(self, period_id: str) -> str:
        period_intent_map = {
            'fixed_yesterday': 'Q_ERR_COUNT_YESTERDAY_ALL_TEAMS',
            'fixed_today': 'Q_ERR_COUNT_TODAY_ALL_TEAMS',
            'fixed_last_24h': 'Q_ERR_COUNT_LAST_24H_ALL_TEAMS',
            'fixed_last_2h': 'Q_ERR_COUNT_LAST_2H_ALL_TEAMS',
            'fixed_this_week': 'Q_ERR_COUNT_THIS_WEEK_ALL_TEAMS',
            'fixed_last_week': 'Q_ERR_COUNT_LAST_WEEK_ALL_TEAMS',
            'fixed_this_month': 'Q_ERR_COUNT_THIS_MONTH_ALL_TEAMS',
            'fixed_last_month': 'Q_ERR_COUNT_LAST_MONTH_ALL_TEAMS',
        }
        return period_intent_map.get(period_id, 'Q_ERR_COUNT_ALL_TIME_ALL_TEAMS')

    # ======================= MAPPED INTENT EXECUTION =======================
    def _execute_mapped_intent(
        self, user_text: str, intent: Dict[str, Any], project_id: Optional[str],
        severity: Optional[str], n_days: Optional[str],
        ticket_id: Optional[str], type_like: Optional[str],
        start_ts: Optional[datetime], end_ts: Optional[datetime],
        repo_name: Optional[str], wants_sql: bool = False
    ) -> Dict[str, Any]:
        """Execute a mapped intent (predefined query from QUERY_CATALOG)."""
        qid = intent.get("query_id")
        if not qid:
            return kv_card("Intent Error", {"error": "Intent missing query_id"})   

        # Base params (project_id is canonical from teams.yml)
        params: Dict[str, Any] = {"project_id": project_id} if project_id else {}

        # Compute time windows based on query type (reuses your helper)
        params = self._compute_time_params(qid, params, start_ts, end_ts)   

        # --- New: extract job params just-in-time ---
        job_type = self._extract_job_type(user_text)          # 'ingestion' | 'publishing' | None
        min_hours = self._extract_min_hours(user_text)        # e.g., 24 (int) or None   

        # Optional parameters
        if "severity" in QUERY_CATALOG.get(qid, {}).get("params", []) and severity:
            params["severity"] = severity
        if qid == "Q_ERR_COUNT_LAST_N_DAYS" and n_days:
            params["n_days"] = int(n_days)
        if qid in ("Q_JOB_TYPE_STATUS_LAST_N_DAYS", "Q_JOB_TYPE_FAILURES_LAST_N_DAYS") and n_days:
            params["n_days"] = int(n_days)
        if "type_like" in QUERY_CATALOG.get(qid, {}).get("params", []) and type_like:
            params["type_like"] = f"%{type_like}%"
        if qid == "Q_JIRA_STATUS_FOR_TICKET" and ticket_id:
            params["ticket_id"] = ticket_id
        if "repo_name" in QUERY_CATALOG.get(qid, {}).get("params", []) and repo_name:
            params["repo_name"] = repo_name

        # --- New: job_status params ---
        if "job_type" in QUERY_CATALOG.get(qid, {}).get("params", []) and job_type:
            params["job_type"] = job_type  # used by job_status QIDs  [2] 
        if "min_hours" in QUERY_CATALOG.get(qid, {}).get("params", []) and min_hours:
            params["min_hours"] = int(min_hours)  # used by Q_JOB_TYPE_LONG_RUNNING  [2] 

        # Execute the mapped query
        qmeta = QUERY_CATALOG.get(qid, {})
        if qmeta.get("type") == "sql":
            sql = qmeta.get("text", "")

            # Inject dynamic schema (database.schema replacement)
            sql = sql.replace("{schema}", self.schema_qual)   

            # Handle optional severity filter placeholders
            if "severity" in qmeta.get("params", []) and "severity" in params:
                sql = sql.replace("{severity_filter}", qmeta.get("severity_sql", "AND severity_level=@severity"))
            else:
                sql = sql.replace("{severity_filter}", "")

            # DEBUG
            print("\n[SQL EXECUTION]")
            print(f" query_id: {qid}")
            print(f" sql: {sql}")
            print(f" params: {params}")

            try:
                ordered = qmeta.get("params", [])
                rows = self.db.fetch_all(sql, params, ordered)  # driver expects named params in 'ordered'   
                print(f" result rows: {len(rows) if rows else 0}")

                # Cap long lists (Teams card size)
                capped_rows = rows[:30] if rows else []

                # Render rows via Adaptive Card
                tname = (project_id or "").replace("_", " ").title() if project_id else ""
                rows_card = table_card(f"List — {tname}", capped_rows, max_rows=30)

                # Build explanation (AI, if configured)
                explanation = self._explain_results_with_ai(user_text, capped_rows)

                # Compose response
                cards = [rows_card]
                payload: Dict[str, Any] = {"type": "composite", "explanation": explanation}

                if wants_sql:
                    sql_info = f"-- T-SQL executed\n{sql}\n\n-- Parameters\n{params}"
                    cards.append(code_block_card("SQL Executed", sql_info))
                    payload["sql"] = sql_info

                payload["cards"] = cards
                return payload

            except Exception as e:
                print(f" ERROR: {e}")
                return kv_card("Query Error", {"error": str(e)})

        elif qmeta.get("type") == "vector":
            return self._handle_vector_query(qid, qmeta)  # placeholder   

        return kv_card("Unknown Query", {"info": "Query type not recognized"})

    # ======================= AI FALLBACK EXECUTION =======================

    def _to_qmark_and_args(self, sql: str, params: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """
        Convert T-SQL with @named parameters into qmark SQL with positional args suitable for pyodbc.
        """
        if not sql:
            return sql, []
        pattern = re.compile(r'@([a-zA-Z_][a-zA-Z0-9_]*)')
        occurrences = pattern.findall(sql)  # may repeat
        if not occurrences:
            return sql, []
        first_order: List[str] = []
        seen = set()
        for name in occurrences:
            if name not in seen:
                seen.add(name)
                first_order.append(name)
        missing = [name for name in first_order if name not in params]
        if missing:
            raise ValueError(f"Missing value(s) for SQL parameter(s): {', '.join('@' + m for m in missing)}")
        qmark_sql = pattern.sub('?', sql)
        args: List[Any] = [params[name] for name in occurrences]
        print("[AI PARAM BINDING] first appearance order:", first_order)
        print("[AI PARAM BINDING] occurrences:", occurrences)
        print("[AI PARAM BINDING] args:", args)
        print("[AI PARAM BINDING] qmark_sql:\n", qmark_sql)
        return qmark_sql, args

    def _execute_ai_fallback(self, ai_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI fallback path:
        1) Ask the AI to generate SQL for the user's question.
        2) Sanitize the SQL (only SELECT; known tables).
        3) Convert @named params -> qmark `?` + positional args (for pyodbc).
        4) Execute and render as a count/percentage/list card.
        """
        if not self.ai:
            return kv_card("AI Unavailable", {"error": "AI client not configured"})

        # 1) Generate SQL from AI
        schema_context = self._build_schema_context()
        user_text = ai_ctx.get("user_text", "")
        sql_query = self._generate_sql_with_ai(user_text, schema_context, ai_ctx.get("project_id"), ai_ctx)
        
        if not sql_query:
            try:
                err_info = getattr(self.ai, "last_error_info", lambda: None)()
            except Exception:
                err_info = None
            print("[AI DEBUG] Empty SQL from AI. Details:", err_info or "<none>")
            # OLD: return kv_card("SQL Generation Failed", {...}) or {"type":"text","content":"OK"}
            # NEW: always guide the user
            return {"type": "text", "content": self.GUIDANCE_MESSAGE}


        # 2) Bind available parameters (dict of named values)
        ai_params: Dict[str, Any] = {}
        if ai_ctx.get("project_id"):
            ai_params["project_id"] = ai_ctx["project_id"]
        if ai_ctx.get("severity"):
            ai_params["severity"] = ai_ctx["severity"]
        if ai_ctx.get("start_ts"):
            ai_params["start_ts"] = ai_ctx["start_ts"]
        if ai_ctx.get("end_ts"):
            ai_params["end_ts"] = ai_ctx["end_ts"]
        if ai_ctx.get("ticket_id"):
            ai_params["ticket_id"] = ai_ctx["ticket_id"]
        if ai_ctx.get("type_like"):
            ai_params["type_like"] = f"%{ai_ctx['type_like']}%"
        if ai_ctx.get("n_days") is not None:
            try:
                ai_params["n_days"] = int(ai_ctx["n_days"])
            except Exception:
                pass

        # Prefer @severity if model hard-coded severity
        try:
            if ai_ctx.get("severity"):
                sql_query = re.sub(
                    r"\bseverity\s*=\s*'(?i:critical|high|medium|low)'\b",
                    "severity_level = @severity",
                    sql_query,
                    flags=re.IGNORECASE
                )
        except Exception:
            pass

        print(f"[AI PARAMS] {ai_params}")

        # 3) Safety: allow only SELECTs and known tables (current schema)
        try:
            allowed_tables = [
                f"{self.sql_database}.{self.sql_schema}.error_logs",
                f"{self.sql_database}.{self.sql_schema}.jira_ticket_details",
                f"{self.sql_database}.{self.sql_schema}.root_causes",
                f"{self.sql_database}.{self.sql_schema}.solutions",
                f"{self.sql_database}.{self.sql_schema}.job_status",
            ]
            sql_query = self._sanitize_sql(sql_query, allowed_tables=allowed_tables)
            print("[AI SQL (rewritten)]", sql_query)
        except Exception as se:
            print(f"[AI SQL BLOCKED] {se} :: {sql_query}")
            return kv_card("Blocked Query", {"error": str(se)})

        # 4) Convert @named params -> qmark `?` + args
        try:
            qmark_sql, qargs = self._to_qmark_and_args(sql_query, ai_params)

            
            param_pattern = re.compile(r'@([a-zA-Z_][a-zA-Z0-9_]*)')
            ordered_param_names = []
            seen = set()
            for name in param_pattern.findall(sql_query):
                if name not in seen and name in ai_params:
                    seen.add(name)
                    ordered_param_names.append(name)

        except Exception as bind_err:
            print(f"[AI PARAM BINDING ERROR] {bind_err}")
            return kv_card("Execution Error", {"error": f"Parameter binding failed: {bind_err}"})

        print(f"[AI SQL (qmark)] {qmark_sql}\n[AI ARGS] {qargs}")

        # 5) Execute and render
        try:
            rows = self.db.fetch_all(sql_query, ai_params, ordered_param_names)
            if not rows:
                return {
                    "type": "composite",
                    "explanation": "I ran the query, but there were no matching results.",
                    "card": kv_card("No Results", {"info": "Query returned no data"})
                }

            if len(rows) == 1:
                row_lower = {str(k).lower(): v for k, v in rows[0].items()}
                # Count result
                if "count" in row_lower:
                    try:
                        cval = int(row_lower.get("count", 0))
                    except Exception:
                        cval = row_lower.get("count", 0)
                    explanation = self._explain_results_with_ai(ai_ctx.get("user_text", ""), rows)
                    cards = [count_card("Result", "", cval)]
                    sql_info = ""
                    if ai_ctx.get("wants_sql"):
                        sql_info = (
                            f"-- T-SQL suggested by AI\n{sql_query}\n\n"
                            f"-- Executed (qmark) + args\n{qmark_sql}\nARGS: {qargs}"
                        )
                        cards.append(code_block_card("SQL Executed", sql_info))
                    return {"type": "composite", "explanation": explanation, "cards": cards, "sql": sql_info}

                # Percentage result
                if "percentage" in row_lower:
                    explanation = self._explain_results_with_ai(ai_ctx.get("user_text", ""), rows)
                    cards = [kv_card("Percentage", {"percentage": row_lower["percentage"]})]
                    sql_info = ""
                    if ai_ctx.get("wants_sql"):
                        sql_info = (
                            f"-- T-SQL suggested by AI\n{sql_query}\n\n"
                            f"-- Executed (qmark) + args\n{qmark_sql}\nARGS: {qargs}"
                        )
                        cards.append(code_block_card("SQL Executed", sql_info))
                    return {"type": "composite", "explanation": explanation, "cards": cards, "sql": sql_info}

            # Default: list/table → Adaptive Card table
            fields = list(rows[0].keys()) if rows else []
            capped_rows = rows[:30]
            table = table_card("Query Results", capped_rows, max_rows=30)
            explanation = self._explain_results_with_ai(ai_ctx.get("user_text", ""), capped_rows)
            cards = [table]
            sql_info = ""
            if ai_ctx.get("wants_sql"):
                sql_info = (
                    f"-- T-SQL suggested by AI\n{sql_query}\n\n"
                    f"-- Executed (qmark) + args\n{qmark_sql}\nARGS: {qargs}"
                )
                cards.append(code_block_card("SQL Executed", sql_info))
            return {"type": "composite", "explanation": explanation, "cards": cards, "sql": sql_info}

        except Exception as e:
            try:
                err_info = getattr(self.ai, "last_error_info", lambda: None)()
            except Exception:
                err_info = None
            print("Query execution error:", e)
            # Return user guidance instead of a raw error message
            return {
                "type": "text",
                "content": self.GUIDANCE_MESSAGE
            }

    
    def _generate_sql_with_ai(self, user_text: str, schema_context: str,
                              project_id: Optional[str], ai_ctx: Dict[str, Any]) -> Optional[str]:
        """Use AI to generate SQL query from user text with parameter hints."""
        # Build "available params" to guide the model
        available_params = []
        if ai_ctx.get("project_id"): available_params.append("@project_id")
        if ai_ctx.get("severity"): available_params.append("@severity")
        if ai_ctx.get("start_ts"): available_params.append("@start_ts")
        if ai_ctx.get("end_ts"): available_params.append("@end_ts")
        if ai_ctx.get("ticket_id"): available_params.append("@ticket_id")
        if ai_ctx.get("type_like"): available_params.append("@type_like")
        if ai_ctx.get("n_days"): available_params.append("@n_days")

        ratio_hint = ""
        tl = (user_text or "").lower()
        if self._contains_any(tl, self.RATIO_TOKENS):
            ratio_hint = """
If the user asks for percentage/share/ratio:
- Return a single row with a column named `percentage` (0-100).
- Compute 100.0 * (team_count) / NULLIF(total_count, 0) using decimal arithmetic.
- Apply any available filters (project_id, severity, time window).
"""

        prompt = f"""You are a SQL Server expert. Generate a valid SQL query to answer the user's question.
DATABASE SCHEMA:
{schema_context}
USER QUESTION:
{user_text}
AVAILABLE NAMED PARAMETERS YOU MAY USE (only if relevant):
{', '.join(available_params) if available_params else '(none)'}
REQUIREMENTS:
1) Generate ONLY valid SQL Server T-SQL
2) Use parameterized queries with @param notation (only from the available list)
3) Return results that directly answer the user's question
4) Always specify column names in SELECT (no SELECT *)
5) Include appropriate JOINs if needed
6) Limit rows if returning raw events (e.g., TOP (100)) and ORDER BY a sensible column
7) Do NOT include explanations, only the SQL query
Note: The current SQL schema name is: {self.sql_schema}
{f'Note: The user is asking about project: {project_id}' if project_id else ''}
{ratio_hint}.
Also,
The following columns are TEXT/NTEXT:
- error_message
- stack_trace
- cleaned_stack_trace

These MUST be CAST to NVARCHAR(4000) if used in GROUP BY or ORDER BY.


"""
        try:
            response = self.ai.generate_text(prompt, max_tokens=900, temperature=0.1)
            if response:
                sql = self._extract_sql_from_response(response)
                print("SQL generated from AI :", sql)
                return sql
            return None
        except Exception as e:
            print(f"Error generating SQL with AI: {e}")
            return None

    def _sanitize_sql(self, sql: str, allowed_tables: List[str]) -> str:
        """
        Safely rewrite AI SQL to use fully-qualified table names,
        without causing prefix duplication.
        """

        import re

        # 1. SELECT-only safety
        lower = sql.strip().lower()
        if not (lower.startswith("select") or lower.startswith("with")):
            raise ValueError("Only SELECT queries allowed.")

        banned = ["insert ", "update ", "delete ", "merge ", "drop ",
                "alter ", "truncate ", "exec ", "execute "]
        if any(b in lower for b in banned):
            raise ValueError("Dangerous SQL keyword found.")

        # -------------------------------------------------------
        # BUILD MAP OF base_name -> fully-qualified-name
        # Example:  "error_logs" -> "AI_PredictiveRecoveryDB.project_1.error_logs"
        # -------------------------------------------------------
        table_map = {}
        for full in allowed_tables:
            base = full.split(".")[-1].lower()   # e.g. error_logs
            table_map[base] = full

        # -------------------------------------------------------
        # ONE-PASS TABLE REWRITE (NO MULTIPLE OVERLAPS)
        # -------------------------------------------------------
        def replace_table(match):
            table = match.group(1).lower()  # captured base table
            return table_map.get(table, match.group(0))

        # Pattern: match table names only when they follow FROM / JOIN / UPDATE / INTO / etc.
        table_pattern = re.compile(
            r"\b(from|join)\s+([a-zA-Z0-9_\.]+)",
            re.IGNORECASE
        )

        def fix(match):
            keyword = match.group(1)
            tbl = match.group(2)

            base = tbl.split(".")[-1].lower()
            if base in table_map:
                return f"{keyword} {table_map[base]}"
            return match.group(0)

        rewritten = table_pattern.sub(fix, sql)

        # -------------------------------------------------------
        # Final check
        # -------------------------------------------------------
        lowered = rewritten.lower()
        if not any(tbl.lower() in lowered for tbl in allowed_tables):
            raise ValueError("Query references unknown tables.")

        return rewritten

    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL query from AI response."""
        match = re.search(r'(SELECT\s+.*?;?\s*)$', response, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1).strip()
            return sql if sql.endswith(';') else sql + ';'
        return response.strip()

    def _build_schema_context(self) -> str:
        """Build database schema description for AI prompt (dynamic schema)."""
        s = self.sql_schema
        schema = f"""
-- Available tables (schema: {s})

1. {s}.error_logs
   - error_id (int, PK, identity)
   - event_timestamp (datetime2(3)) -- UTC error occurrence time
   - error_tool (varchar)           -- tech stack: Python/Java/SQL/etc
   - project_id (varchar)           -- logical team/project
   - repo_name (varchar)
   - error_message (text)           -- main error label/header
   - stack_trace (text)             -- raw trace
   - cleaned_stack_trace (text)     -- trace with numbers/timestamps removed (embedding)
   - severity_level (text)          -- e.g., HIGH/MEDIUM/LOW/CRITICAL
   - occurrence_count (int)         -- similar occurrences (default 1)
   - solution_id (int, FK -> {s}.solutions.solution_id)
   - root_cause_id (int, FK -> {s}.root_causes.root_cause_id)
   - jira_id (int, FK -> {s}.jira_ticket_details.jira_id)
   - processed (bit)                -- triage marker

2. {s}.jira_ticket_details
   - jira_id (int, PK, identity)
   - ticket_id (nvarchar(50))
   - error_id (int, nullable)       -- link to a specific error row (optional)
   - jira_title (nvarchar(255))
   - description (nvarchar(max))
   - solution_id (int, nullable)
   - created_at (datetime2(7))
   - updated_at (datetime2(7))

3. {s}.root_causes
   - root_cause_id (int, PK, identity)
   - error_id (int, NOT NULL)
   - root_cause (nvarchar(max))
   - created_at (datetime2(3))
   - updated_at (datetime2(3), nullable)

4. {s}.solutions
   - solution_id (int, PK, identity)
   - error_id (int, NOT NULL)
   - proposed_solution (nvarchar(max))
   - applied_solution (nvarchar(max))
   - confidence_score (decimal(5,2))
   - final_solution_source (varchar(30))
   - created_at (datetime2(3))
   - updated_at (datetime2(3), nullable)

4. {s}.job_status
 - id (int, PK, identity)
 - start_time (datetime2(3))
 - end_time   (datetime2(3))
 - job_type (varchar)
 - success_tag, failure_tag, running_tag (varchar)
 - success_count, failure_count, running_count (int)


Notes:
- Use event_timestamp for all time filters (formerly occurred_at).
- Use severity_level for severity (formerly severity).
- project_id identifies the team/project.
- For Jira linking, prefer: error_logs.jira_id = jira_ticket_details.jira_id
  or error_logs.error_id = jira_ticket_details.error_id (when present).
"""
        return schema.strip()

    # ======================= PARAMETER EXTRACTION =======================

    def _normalize(self, s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^a-z0-9]+", " ", s)  # convert _, -, /, + etc to space
        return re.sub(r"\s+", " ", s).strip()

    def _extract_from_aliases(self, text: str, mapping: dict) -> Optional[str]:
        t = self._normalize(text)
        for key, meta in (mapping or {}).items():
            if self._normalize(key) in t:
                return key
            for alias in (meta or {}).get("aliases", []):
                if self._normalize(alias) in t:
                    return key
        return None

    def _extract_team_key(self, text: str):
        return self._extract_from_aliases(text, self.teams_alias)

    def _extract_repo_name(self, text: str) -> Optional[str]:
        return self._extract_from_aliases(text, self.repo_alias)

    def _extract_severity(self, text: str) -> Optional[str]:
        """Extract severity level from text"""
        tl = (text or "").lower()
        for key, val in SEVERITY_MAP.items():
            if key in tl:
                return val
        return None

    def _extract_n_days(self, text: str) -> Optional[str]:
        """Extract number of days (e.g., 'last 7 days')"""
        match = re.search(r'last\s+(\d+)\s+days?', text)
        return match.group(1) if match else None

    def _extract_ticket_id(self, text: str) -> Optional[str]:
        """Extract Jira ticket ID (e.g., PROJ-123)"""
        match = re.search(r'([A-Z]+[-]?\d+)', text)
        return match.group(1) if match else None

    def _extract_exception_like(self, text: str) -> Optional[str]:
        """Extract exception type pattern"""
        patterns = ["nullpointer", "timeout", "connection", "memory", "permission"]
        tl = (text or "").lower()
        for pattern in patterns:
            if pattern in tl:
                return pattern
        return None
    
    def _extract_job_type(self, text: str) -> Optional[str]:
        """Return 'ingestion' or 'publishing' if mentioned."""
        tl = (text or "").lower()
        if "ingest" in tl or "ingestion" in tl:
            return "ingestion"
        if "publishing" in tl or "publish" in tl or "publisher" in tl:
            return "publishing"
        return None

    def _extract_min_hours(self, text: str) -> Optional[int]:
        """Extract min hours for long-running jobs (e.g., '24h', '>= 12 hours')."""
        m = re.search(r'(?:>=?|over|more than|from)?\s*(\d+)\s*(?:h|hr|hrs|hours?)', (text or '').lower())
        return int(m.group(1)) if m else None

    def _extract_date_range(self, text: str):
        """
        Extracts two timestamps from queries like:
        'between 2026-03-24 08:58:05.000 and 2026-03-24 09:30:00.000'
        """
        import re
        from datetime import datetime

        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})'
        matches = re.findall(pattern, text)

        if len(matches) >= 2:
            try:
                s = datetime.strptime(matches[0], "%Y-%m-%d %H:%M:%S.%f")
                e = datetime.strptime(matches[1], "%Y-%m-%d %H:%M:%S.%f")
                return s, e
            except Exception:
                return None, None

        return None, None

    def _extract_period_id(self, text: str) -> Optional[str]:
        """Extract time period identifier from text"""
        tl = (text or "").lower()
        if "today" in tl:
            return "fixed_today"
        if "yesterday" in tl:
            return "fixed_yesterday"
        if "this week" in tl:
            return "fixed_this_week"
        if "last week" in tl:
            return "fixed_last_week"
        if "this month" in tl:
            return "fixed_this_month"
        if "last month" in tl:
            return "fixed_last_month"
        if ("last 24 hour" in tl or "past 24 hour" in tl or
            "last 24 hours" in tl or "past 24 hours" in tl or "24h" in tl):
            return "fixed_last_24h"
        if "last 2 hour" in tl or "last 2 hours" in tl:
            return "fixed_last_2h"
        return None

    # ======================= TIME PARAMETER COMPUTATION =======================

    def _compute_time_params(self, qid: str, params: Dict[str, Any],
                             start_ts: Optional[datetime], end_ts: Optional[datetime]) -> Dict[str, Any]:
        """Compute and add time window parameters based on query type"""

        if qid in ("Q_ERR_COUNT_TODAY_BY_TEAM",
                   "Q_ERR_COUNT_TODAY_BY_TEAM_AND_SEVERITY",
                   "Q_ERR_COUNT_TODAY_ALL_TEAMS",
                   "Q_ERRORS_TODAY_LIST"):
            params["start_ts"] = today_start_utc()

        if qid in ("Q_JIRA_TICKETS_TODAY",
                   "Q_ERRORS_BY_EXCEPTION_TODAY"):
            params["today_start"] = today_start_utc()

        if qid in ("Q_ERR_COUNT_YESTERDAY_BY_TEAM",
                   "Q_ERR_COUNT_YESTERDAY_ALL_TEAMS",
                   "Q_ERRORS_YESTERDAY_LIST"):
            s, e = yesterday_bounds_utc()
            params["start_ts"], params["end_ts"] = s, e

        if qid in ("Q_ERR_COUNT_THIS_WEEK_BY_TEAM",
                   "Q_ERR_COUNT_THIS_WEEK_ALL_TEAMS"):
            params["start_ts"] = this_week_start_utc()

        if qid in ("Q_ERR_COUNT_LAST_WEEK_BY_TEAM",
                   "Q_FAILURE_RATE_LAST_WEEK",
                   "Q_ERR_COUNT_LAST_WEEK_ALL_TEAMS"):
            ls, ts = last_week_bounds_utc()
            params["last_week_start"], params["this_week_start"] = ls, ts

        if qid in ("Q_ERR_COUNT_LAST_WEEK_BY_TEAM",
                   "Q_ERR_COUNT_LAST_WEEK_ALL_TEAMS"):
            ls, ts = last_week_bounds_utc()
            params["start_ts"], params["end_ts"] = ls, ts

        if qid in ("Q_ERR_COUNT_THIS_MONTH_BY_TEAM",
                   "Q_ERR_COUNT_THIS_MONTH_ALL_TEAMS"):
            params["start_ts"] = this_month_start_utc()

        if qid in ("Q_ERR_COUNT_LAST_MONTH_BY_TEAM",
                   "Q_ERR_COUNT_LAST_MONTH_ALL_TEAMS"):
            s, e = last_month_bounds_utc()
            params["start_ts"], params["end_ts"] = s, e

        if qid == "Q_ERRORS_BY_DATE_RANGE" and start_ts and end_ts:
            params["start_ts"], params["end_ts"] = start_ts, end_ts

        
        # job_status — today windows
        if qid in (
            "Q_JOB_TYPE_STATUS_TODAY",
            "Q_JOB_TYPE_FAILURES_TODAY",
            "Q_PRODUCT_HEALTH_TODAY",
            "Q_JOB_FAILURE_RATE_TODAY",
            "Q_JOB_TYPE_FAILURE_RATE_TODAY"
        ):
            params["start_ts"] = today_start_utc()

        if qid == "Q_PRODUCT_HEALTH_BY_DATE_RANGE" and start_ts and end_ts:
            params["start_ts"] = start_ts
            params["end_ts"] = end_ts



        return params

    # ======================= RENDERING / VECTOR PLACEHOLDER ====================

    def _render_sql_card(self, qid: str, rows: List[Dict[str, Any]], project_id: Optional[str]) -> Dict[str, Any]:
        tname = project_id.replace("_", " ").title() if project_id else ""
        if qid.startswith("Q_ERR_COUNT") or qid in ("Q_WEEKEND_FAILURES",):
            cnt = int(rows[0]["failure_count"]) if rows else 0
            return count_card(f"Failures — {tname}", "", cnt)
        if qid in ("Q_HOURLY_BREAKDOWN_LAST_24H", "Q_WEEKLY_TREND", "Q_DAILY_TREND", "Q_LAST_7D_TREND"):
            return list_card(f"Trend — {tname}", rows, fields=list(rows[0].keys()) if rows else [])
        if qid in ("Q_TOP_ERROR_TYPES", "Q_TOP_ERROR_TYPES_24H"):
            return list_card(f"Top breakdown — {tname}", rows, fields=list(rows[0].keys()) if rows else [])
        if qid in (
            "Q_LIST_ALL_ERRORS", "Q_ERRORS_TODAY_LIST", "Q_ERRORS_LAST_24H_LIST", "Q_ERRORS_YESTERDAY_LIST",
            "Q_LATEST_10_FAILURES", "Q_UNPROCESSED_ERRORS"
        ):
            return list_card(f"List — {tname}", rows, fields=list(rows[0].keys()) if rows else [])
        return list_card("Results", rows, fields=list(rows[0].keys()) if rows else [])

    def _handle_vector_query(self, qid: str, qmeta: Dict[str, Any]) -> Dict[str, Any]:
        return kv_card("Vector search", {"info": "Vector queries not yet implemented in AI fallback"})

    def _explain_results_with_ai(self, user_text: str, rows: List[Dict[str, Any]]) -> str:
        if not self.ai:
            return "Explanation unavailable (AI client not configured)."
        if not rows:
            return "No records for your question."
        preview = rows[:5]
        fields = list(preview[0].keys()) if preview else []
        text_l = (user_text or "").lower()
        if self._contains_any(text_l, self.WHY_TOKENS):
            ptype = "rca"
        elif self._contains_any(text_l, self.RATIO_TOKENS):
            ptype = "ratio"
        elif self._contains_any(text_l, self.COMPARE_TOKENS):
            ptype = "compare"
        elif self._contains_any(text_l, self.STATS_TOKENS):
            ptype = "summary"
        elif any(k in text_l for k in ["trend", "increase", "decrease", "spike", "drop"]):
            ptype = "trend"
        elif self._contains_any(text_l, self.DISTINCT_TOKENS):
            ptype = "distinct"
        else:
            ptype = "summary"

        team_key = None
        try:
            team_key = self._extract_team_key(text_l)
        except Exception:
            pass

        resolver = get_resolver()
        template, gen_params = resolver.get(ptype, team_key=team_key)
        prompt = resolver.render(
            template,
            user_text=user_text,
            fields=fields,
            preview=preview,
        )
        try:
            explanation = self.ai.generate_text(
                prompt,
                max_tokens=gen_params.get("max_tokens", 350),
                temperature=gen_params.get("temperature", 0.4),
            )
            return explanation or "I retrieved the data, but could not generate an explanation."
        except Exception:
            return "I retrieved the data, but could not generate an explanation."