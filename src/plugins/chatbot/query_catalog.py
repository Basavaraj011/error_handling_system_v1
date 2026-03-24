# src/plugins/chatbot/query_catalog.py
# Maps query_id -> {type, text, params}
# type: "sql" (SQL Server) or "vector" (semantic search via VectorStore)

QUERY_CATALOG = {
    # --------------------- ALL TEAMS: BASIC & PERIOD COUNTS ---------------------
    "Q_ERR_COUNT_ALL_TIME_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE 1=1 {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_TODAY_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_YESTERDAY_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts AND event_timestamp < @end_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "end_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_LAST_24H_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= DATEADD(HOUR, -24, SYSUTCDATETIME()) {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_LAST_2H_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= DATEADD(HOUR, -2, SYSUTCDATETIME()) {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_THIS_WEEK_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_LAST_WEEK_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts AND event_timestamp < @end_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "end_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_THIS_MONTH_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_LAST_MONTH_ALL_TEAMS": {
        "type": "sql",
        "text": """
        SELECT project_id, COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE event_timestamp >= @start_ts AND event_timestamp < @end_ts {severity_filter}
        GROUP BY project_id
        ORDER BY failure_count DESC;
        """,
        "params": ["start_ts", "end_ts", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },

    # --------------------- BASIC COUNTS ---------------------
    "Q_ERR_COUNT_ALL_TIME_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
        {severity_filter};
        """,
        "params": ["project_id", "severity"],
        "severity_sql": "AND severity_level = @severity",
    },
    "Q_ERR_COUNT_LAST_24H_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= DATEADD(HOUR, -24, SYSUTCDATETIME());
        """,
        "params": ["project_id"],
    },
    "Q_ERR_COUNT_YESTERDAY_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts
          AND event_timestamp < @end_ts;
        """,
        "params": ["project_id", "start_ts", "end_ts"],
    },
    "Q_ERR_COUNT_TODAY_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts;
        """,
        "params": ["project_id", "start_ts"],
    },
    "Q_ERR_COUNT_THIS_WEEK_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts;
        """,
        "params": ["project_id", "start_ts"],
    },
    "Q_ERR_COUNT_LAST_WEEK_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts AND event_timestamp < @end_ts;
        """,
        "params": ["project_id", "start_ts", "end_ts"],
    },
    "Q_ERR_COUNT_THIS_MONTH_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts;
        """,
        "params": ["project_id", "start_ts"],
    },
    "Q_ERR_COUNT_LAST_MONTH_BY_TEAM": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts AND event_timestamp < @end_ts;
        """,
        "params": ["project_id", "start_ts", "end_ts"],
    },
    "Q_ERR_COUNT_LAST_24H_BY_TEAM_AND_SEVERITY": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= DATEADD(HOUR, -24, SYSUTCDATETIME())
          AND severity_level = @severity;
        """,
        "params": ["project_id", "severity"],
    },
    "Q_ERR_COUNT_TODAY_BY_TEAM_AND_SEVERITY": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= @start_ts
          AND severity_level = @severity;
        """,
        "params": ["project_id", "start_ts", "severity"],
    },
    "Q_ERR_COUNT_LAST_2H": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= DATEADD(HOUR, -2, SYSUTCDATETIME());
        """,
        "params": ["project_id"],
    },
    "Q_ERR_COUNT_LAST_N_DAYS": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= DATEADD(DAY, -@n_days, SYSUTCDATETIME());
        """,
        "params": ["project_id", "n_days"],
    },

    # --------------------- LISTS / FILTERS --------------------
    "Q_LIST_ALL_ERRORS": {
        "type": "sql",
        "text": """
        SELECT TOP (100)
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id"],
    },
    "Q_LATEST_10_FAILURES": {
        "type": "sql",
        "text": """
        SELECT TOP (10)
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id"],
    },
    "Q_UNPROCESSED_ERRORS": {
        "type": "sql",
        "text": """
        SELECT TOP (50)
            error_id AS id,
            event_timestamp,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND processed=0
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id"],
    },
    "Q_ERRORS_BY_TYPE": {
        "type": "sql",
        "text": """
        SELECT TOP (50)
            error_id AS id,
            event_timestamp,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND error_message LIKE @type_like
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id", "type_like"],
    },
    "Q_ERRORS_BY_EXCEPTION_TODAY": {
        "type": "sql",
        "text": """
        SELECT TOP (50)
            error_id AS id,
            event_timestamp,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp>=@today_start
          AND error_message LIKE @type_like
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id", "today_start", "type_like"],
    },
    "Q_ERRORS_BY_DATE_RANGE": {
        "type": "sql",
        "text": """
        SELECT
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp>=@start_ts AND event_timestamp<@end_ts
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id", "start_ts", "end_ts"],
    },
    "Q_ERRORS_TODAY_LIST": {
        "type": "sql",
        "text": """
        SELECT TOP (100)
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp >= @start_ts
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id", "start_ts"],
    },
    "Q_ERRORS_LAST_24H_LIST": {
        "type": "sql",
        "text": """
        SELECT TOP (100)
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp >= DATEADD(HOUR, -24, SYSUTCDATETIME())
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id"],
    },
    "Q_ERRORS_YESTERDAY_LIST": {
        "type": "sql",
        "text": """
        SELECT TOP (100)
            error_id AS id,
            event_timestamp,
            severity_level AS severity,
            error_message
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp >= @start_ts
          AND event_timestamp <  @end_ts
        ORDER BY event_timestamp DESC;
        """,
        "params": ["project_id", "start_ts", "end_ts"],
    },

    # --------------------- TRENDS / ANALYTICS -----------------
    "Q_HOURLY_BREAKDOWN_LAST_24H": {
        "type": "sql",
        "text": """
        SELECT DATEPART(HOUR, event_timestamp) AS hour_utc,
               COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND event_timestamp >= DATEADD(HOUR, -24, SYSUTCDATETIME())
        GROUP BY DATEPART(HOUR, event_timestamp)
        ORDER BY hour_utc;
        """,
        "params": ["project_id"],
    },
    "Q_WEEKLY_TREND": {
        "type": "sql",
        "text": """
        SELECT CAST(event_timestamp AS DATE) AS d, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND event_timestamp>=DATEADD(DAY,-7,SYSUTCDATETIME())
        GROUP BY CAST(event_timestamp AS DATE)
        ORDER BY d;
        """,
        "params": ["project_id"],
    },
    "Q_DAILY_TREND": {
        "type": "sql",
        "text": """
        SELECT CAST(event_timestamp AS DATE) AS d, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND event_timestamp>=DATEADD(DAY,-30,SYSUTCDATETIME())
        GROUP BY CAST(event_timestamp AS DATE)
        ORDER BY d;
        """,
        "params": ["project_id"],
    },
    "Q_HEATMAP_FAILURES": {
        "type": "sql",
        "text": """
        SELECT DATENAME(WEEKDAY, event_timestamp) AS dow,
               DATEPART(HOUR, event_timestamp) AS hh,
               COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND event_timestamp>=DATEADD(DAY,-14,SYSUTCDATETIME())
        GROUP BY DATENAME(WEEKDAY, event_timestamp), DATEPART(HOUR, event_timestamp)
        ORDER BY dow, hh;
        """,
        "params": ["project_id"],
    },
    "Q_TOP_FAILURE_HOUR": {
        "type": "sql",
        "text": """
        SELECT TOP (1) DATEPART(HOUR, event_timestamp) AS hour_utc, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND event_timestamp>=DATEADD(DAY,-7,SYSUTCDATETIME())
        GROUP BY DATEPART(HOUR, event_timestamp)
        ORDER BY cnt DESC;
        """,
        "params": ["project_id"],
    },

    # “Top error types” now uses error_tool grouping (Python/Java/SQL/…)
    "Q_TOP_ERROR_TYPES": {
        "type": "sql",
        "text": """
        SELECT TOP (5) error_tool AS error_category, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id
        GROUP BY error_tool
        ORDER BY cnt DESC;
        """,
        "params": ["project_id"],
    },
    "Q_TOP_ERROR_TYPES_24H": {
        "type": "sql",
        "text": """
        SELECT TOP (10) error_tool AS error_category, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id
          AND event_timestamp >= DATEADD(HOUR,-24,SYSUTCDATETIME())
        GROUP BY error_tool
        ORDER BY cnt DESC;
        """,
        "params": ["project_id"],
    },

    "Q_FAILURE_RATE_LAST_WEEK": {
        "type": "sql",
        "text": """
        SELECT
          SUM(CASE WHEN event_timestamp >= @this_week_start THEN 1 ELSE 0 END) AS this_week,
          SUM(CASE WHEN event_timestamp >= @last_week_start AND event_timestamp < @this_week_start THEN 1 ELSE 0 END) AS last_week
        FROM {schema}.error_logs
        WHERE project_id=@project_id;
        """,
        "params": ["project_id", "this_week_start", "last_week_start"],
    },
    "Q_LAST_7D_TREND": {
        "type": "sql",
        "text": """
        SELECT CAST(event_timestamp AS DATE) AS d, COUNT(*) AS cnt
        FROM {schema}.error_logs
        WHERE project_id=@project_id AND event_timestamp>=DATEADD(DAY,-7,SYSUTCDATETIME())
        GROUP BY CAST(event_timestamp AS DATE)
        ORDER BY d;
        """,
        "params": ["project_id"],
    },

    # --------------------- JIRA (adapted to jira_ticket_details) ----------------
    "Q_JIRA_OPEN_TICKETS": {
        "type": "sql",
        "text": """
        SELECT TOP (20)
            jt.ticket_id,
            jt.jira_title,
            jt.created_at,
            jt.updated_at
        FROM {schema}.jira_ticket_details jt
        INNER JOIN {schema}.error_logs el
            ON el.jira_id = jt.jira_id OR el.error_id = jt.error_id
        WHERE el.project_id = @project_id
        ORDER BY jt.created_at DESC;
        """,
        "params": ["project_id"],
    },
    "Q_JIRA_TICKETS_TODAY": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS ticket_count
        FROM {schema}.jira_ticket_details jt
        INNER JOIN {schema}.error_logs el
            ON el.jira_id = jt.jira_id OR el.error_id = jt.error_id
        WHERE el.project_id=@project_id AND jt.created_at>=@today_start;
        """,
        "params": ["project_id", "today_start"],
    },
    "Q_JIRA_TICKETS_24H": {
        "type": "sql",
        "text": """
        SELECT jt.ticket_id, jt.created_at, jt.updated_at
        FROM {schema}.jira_ticket_details jt
        INNER JOIN {schema}.error_logs el
            ON el.jira_id = jt.jira_id OR el.error_id = jt.error_id
        WHERE el.project_id=@project_id AND jt.created_at>=DATEADD(HOUR,-24,SYSUTCDATETIME())
        ORDER BY jt.created_at DESC;
        """,
        "params": ["project_id"],
    },
    "Q_JIRA_FOR_LATEST_FAILURE": {
        "type": "sql",
        "text": """
        SELECT TOP (1) jt.ticket_id, jt.jira_title, jt.created_at
        FROM {schema}.error_logs el
        INNER JOIN {schema}.jira_ticket_details jt
            ON el.jira_id = jt.jira_id OR el.error_id = jt.error_id
        WHERE el.project_id=@project_id
        ORDER BY el.event_timestamp DESC;
        """,
        "params": ["project_id"],
    },
    "Q_JIRA_STATUS_FOR_TICKET": {
        "type": "sql",
        "text": """
        SELECT ticket_id, jira_title, created_at, updated_at
        FROM {schema}.jira_ticket_details
        WHERE ticket_id=@ticket_id;
        """,
        "params": ["ticket_id"],
    },

    # --------------------- RCA / SOLUTIONS -------------------
    "Q_RCA_HISTORY_FOR_PATTERN": {
        "type": "sql",
        "text": """
        SELECT TOP (20)
            r.error_id,
            r.root_cause,
            r.created_at
        FROM {schema}.root_causes r
        INNER JOIN {schema}.error_logs el ON el.error_id = r.error_id
        WHERE el.project_id=@project_id AND r.error_id=@pattern_id
        ORDER BY r.created_at DESC;
        """,
        "params": ["project_id", "pattern_id"],  # pattern_id carries error_id here
    },

    # --------------------- WEEKEND FAILURES ------------------
    "Q_WEEKEND_FAILURES": {
        "type": "sql",
        "text": """
        SELECT COUNT(*) AS failure_count
        FROM {schema}.error_logs
        WHERE project_id = @project_id
          AND DATENAME(WEEKDAY, event_timestamp) IN ('Saturday','Sunday');
        """,
        "params": ["project_id"],
    },

    # --------------------- VECTOR (placeholders) --------------
    "Q_VECTOR_SIMILAR_ERRORS": {
        "type": "vector",
        "params": ["project_id", "query_text", "top_k", "min_score"],
    },
    "Q_VECTOR_MATCH_RCA": {
        "type": "vector",
        "params": ["project_id", "query_text", "top_k", "min_score"],
    },
    "Q_VECTOR_SIMILAR_PATTERNS": {
        "type": "vector",
        "params": ["project_id", "query_text", "top_k", "min_score"],
    },
    "Q_ERROR_LAST_OCCURRED": {
        "type": "vector",
        "params": ["project_id", "query_text", "top_k", "min_score"],
    },
    "Q_ERROR_IS_RECURRING": {
        "type": "vector",
        "params": ["project_id", "query_text", "top_k", "min_score"],
    },

# ========================================================================
# --------------------- JOB STATUS (COMPLETE CATALOG) --------------------
# ========================================================================

# ====================== GLOBAL STATUS (ALL JOB TYPES) ===================

    "Q_JOB_STATUS_TODAY": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= @start_ts
            GROUP BY job_type
            ORDER BY job_type;
        """,
        "params": ["start_ts"]
    },

    "Q_JOB_STATUS_YESTERDAY": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= @start_ts
            AND start_time < @end_ts
            GROUP BY job_type
            ORDER BY job_type;
        """,
        "params": ["start_ts", "end_ts"]
    },

    "Q_JOB_STATUS_LAST_24H": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(HOUR, -24, SYSUTCDATETIME())
            GROUP BY job_type
            ORDER BY job_type;
        """,
        "params": []
    },

    "Q_JOB_STATUS_LAST_N_DAYS": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(DAY, -@n_days, SYSUTCDATETIME())
            GROUP BY job_type
            ORDER BY job_type;
        """,
        "params": ["n_days"]
    },


    # ==================== STATUS FOR A SPECIFIC JOB TYPE ====================

    "Q_JOB_TYPE_STATUS_TODAY": {
        "type": "sql",
        "text": """
            SELECT 
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= @start_ts;
        """,
        "params": ["job_type", "start_ts"]
    },

    "Q_JOB_TYPE_STATUS_LAST_N_DAYS": {
        "type": "sql",
        "text": """
            SELECT 
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= DATEADD(DAY, -@n_days, SYSUTCDATETIME());
        """,
        "params": ["job_type", "n_days"]
    },


    # =========================== PRODUCT HEALTH ==============================

    "Q_PRODUCT_HEALTH_TODAY": {
        "type": "sql",
        "text": """
            SELECT 
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= @start_ts;
        """,
        "params": ["start_ts"]
    },

    "Q_PRODUCT_HEALTH_LAST_24H": {
        "type": "sql",
        "text": """
            SELECT 
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(HOUR, -24, SYSUTCDATETIME());
        """,
        "params": []
    },


    # =============================== FAILURES ================================

    "Q_JOB_TYPE_FAILURES_TODAY": {
        "type": "sql",
        "text": """
            SELECT SUM(failure_count) AS failures
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= @start_ts;
        """,
        "params": ["job_type", "start_ts"]
    },

    "Q_JOB_TYPE_FAILURES_LAST_N_DAYS": {
        "type": "sql",
        "text": """
            SELECT SUM(failure_count) AS failures
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= DATEADD(DAY, -@n_days, SYSUTCDATETIME());
        """,
        "params": ["job_type", "n_days"]
    },


    # ============================= RUNNING JOBS ==============================

    "Q_JOB_TYPE_RUNNING_NOW": {
        "type": "sql",
        "text": """
            SELECT 
                COALESCE(running_count, 0) AS running
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= DATEADD(DAY, -1, SYSUTCDATETIME())
            ORDER BY start_time DESC
            OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY;
        """,
        "params": ["job_type"]
    },


    # ========================== LONG-RUNNING JOBS ============================

    "Q_JOB_TYPE_LONG_RUNNING": {
        "type": "sql",
        "text": """
            SELECT TOP (100)
                job_type,
                start_time,
                end_time,
                DATEDIFF(HOUR, start_time, end_time) AS hours_running
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND DATEDIFF(HOUR, start_time, end_time) >= @min_hours
            ORDER BY hours_running DESC;
        """,
        "params": ["job_type", "min_hours"]
    },

    "Q_ALL_LONG_RUNNING_JOBS": {
        "type": "sql",
        "text": """
            SELECT TOP (100)
                job_type,
                start_time,
                end_time,
                DATEDIFF(HOUR, start_time, end_time) AS hours_running
            FROM {schema}.job_status
            WHERE DATEDIFF(HOUR, start_time, end_time) >= @min_hours
            ORDER BY hours_running DESC;
        """,
        "params": ["min_hours"]
    },


    # ================================ LISTS =================================

    "Q_JOB_LIST_LAST_24H": {
        "type": "sql",
        "text": """
            SELECT TOP (100)
                id,
                job_type,
                start_time,
                end_time,
                success_count,
                failure_count,
                running_count
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(HOUR, -24, SYSUTCDATETIME())
            ORDER BY start_time DESC;
        """,
        "params": []
    },


    # ============================== ANALYTICS ================================

    "Q_JOB_HOURLY_TREND_24H": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                DATEPART(HOUR, start_time) AS hour_utc,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(HOUR, -24, SYSUTCDATETIME())
            GROUP BY job_type, DATEPART(HOUR, start_time)
            ORDER BY job_type, hour_utc;
        """,
        "params": []
    },

    "Q_JOB_DAILY_TREND_30D": {
        "type": "sql",
        "text": """
            SELECT 
                CAST(start_time AS DATE) AS day,
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(DAY, -30, SYSUTCDATETIME())
            GROUP BY CAST(start_time AS DATE), job_type
            ORDER BY day, job_type;
        """,
        "params": []
    },

    "Q_JOB_WEEKLY_TREND_8W": {
        "type": "sql",
        "text": """
            SELECT 
                DATEPART(WEEK, start_time) AS week_no,
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(WEEK, -8, SYSUTCDATETIME())
            GROUP BY DATEPART(WEEK, start_time), job_type
            ORDER BY week_no, job_type;
        """,
        "params": []
    },

    "Q_JOB_FAILURE_HEATMAP": {
        "type": "sql",
        "text": """
            SELECT
                DATENAME(WEEKDAY, start_time) AS weekday,
                DATEPART(HOUR, start_time) AS hour_utc,
                job_type,
                SUM(failure_count) AS failures
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(DAY, -14, SYSUTCDATETIME())
            GROUP BY DATENAME(WEEKDAY, start_time), DATEPART(HOUR, start_time), job_type
            ORDER BY weekday, hour_utc;
        """,
        "params": []
    },

    "Q_TOP_JOB_FAILURE_TYPES_7D": {
        "type": "sql",
        "text": """
            SELECT TOP (5)
                job_type,
                SUM(failure_count) AS failures
            FROM {schema}.job_status
            WHERE start_time >= DATEADD(DAY, -7, SYSUTCDATETIME())
            GROUP BY job_type
            ORDER BY failures DESC;
        """,
        "params": []
    },


    # ================================ RATE ==================================

    "Q_JOB_FAILURE_RATE_TODAY": {
        "type": "sql",
        "text": """
            SELECT 
                CAST(100.0 * SUM(failure_count)
                    / NULLIF(SUM(success_count + failure_count), 0)
                AS DECIMAL(5,2)) AS failure_rate_pct
            FROM {schema}.job_status
            WHERE start_time >= @start_ts;
        """,
        "params": ["start_ts"]
    },

    "Q_JOB_TYPE_FAILURE_RATE_TODAY": {
        "type": "sql",
        "text": """
            SELECT 
                CAST(100.0 * SUM(failure_count)
                    / NULLIF(SUM(success_count + failure_count), 0)
                AS DECIMAL(5,2)) AS failure_rate_pct
            FROM {schema}.job_status
            WHERE job_type = @job_type
            AND start_time >= @start_ts;
        """,
        "params": ["job_type", "start_ts"]
    },


    # ============================ ALL-TIME SUMMARY ==========================

    "Q_JOB_SUMMARY_ALL_TIME": {
        "type": "sql",
        "text": """
            SELECT 
                job_type,
                SUM(success_count) AS successes,
                SUM(failure_count) AS failures,
                SUM(running_count) AS running
            FROM {schema}.job_status
            GROUP BY job_type
            ORDER BY job_type;
        """,
        "params": []
    },

    "Q_PRODUCT_HEALTH_BY_DATE_RANGE": {
            "type": "sql",
            "text": """
                SELECT
                    SUM(success_count) AS successes,
                    SUM(failure_count) AS failures,
                    SUM(running_count) AS running
                FROM {schema}.job_status
                WHERE start_time >= @start_ts
                AND start_time < @end_ts;
            """,
            "params": ["start_ts", "end_ts"]
        }
}