"""
Database Manager for SQL Server connections (pyodbc, positional params)
"""
import re
import pyodbc
from typing import List, Dict, Any, Optional, Sequence, Tuple
import logging

logger = logging.getLogger(__name__)

# Regex to find @param placeholders
_QMARK_RE = re.compile(r"@(\w+)")

def _to_qmark_and_args(sql: str,
                       params: Optional[Dict[str, Any]],
                       ordered_param_names: Optional[Sequence[str]]) -> Tuple[str, Tuple[Any, ...]]:
    """
    Convert named parameters (@name) to qmark (?) and return positional args in the provided order.
    - sql: SQL that may contain @param
    - params: dict of values (may be None)
    - ordered_param_names: list/tuple of names in positional order
    """
    qmark_sql = _QMARK_RE.sub("?", sql)
    if not params or not ordered_param_names:
        return qmark_sql, tuple()
    args = tuple(params[name] for name in ordered_param_names if name in params)
    return qmark_sql, args


class DatabaseManager:
    """Manages SQL Server connections"""

    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: SQL Server connection string
                e.g., "Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=db;UID=user;PWD=pass;Encrypt=no;"
                or    "Driver={ODBC Driver 18 for SQL Server};Server=localhost\\SQLEXPRESS;Database=db;Trusted_Connection=yes;Encrypt=no;"
        """
        self.connection_string = connection_string
        self.connection = None
        self._connect()

    def _connect(self):
        """Establish connection to SQL Server"""
        try:
            self.connection = pyodbc.connect(self.connection_string)
            self.connection.autocommit = True
            logger.info("Connected to SQL Server")
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server: {e}", exc_info=True)
            raise

    # -------------------- SELECT helpers --------------------

    def fetch_all(self,
                  query: str,
                  params: Optional[Dict[str, Any]] = None,
                  ordered_param_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return all results as dicts.

        Args:
            query: SQL query with @param placeholders (will be converted to ?)
            params: Dict of parameters {param_name: value}
            ordered_param_names: parameter names IN ORDER to map to ?

        Returns:
            List of result rows as dictionaries
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            qmark_sql, args = _to_qmark_and_args(query, params, ordered_param_names)

            logger.debug("[DB] SQL:\n%s", qmark_sql)
            logger.debug("[DB] ARGS: %s", args)

            cursor.execute(qmark_sql, args)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return results

        except Exception as e:
            logger.error(f"Query execution error: {e}", exc_info=True)
            raise
        finally:
            if cursor is not None:
                cursor.close()

    def fetch_one(self,
                  query: str,
                  params: Optional[Dict[str, Any]] = None,
                  ordered_param_names: Optional[Sequence[str]] = None) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return first result"""
        results = self.fetch_all(query, params, ordered_param_names)
        return results[0] if results else None

    # -------------------- DML helpers --------------------

    def execute(self,
                query: str,
                params: Optional[Dict[str, Any]] = None,
                ordered_param_names: Optional[Sequence[str]] = None) -> int:
        """Execute INSERT/UPDATE/DELETE query. Returns rows affected."""
        cursor = None
        try:
            cursor = self.connection.cursor()
            qmark_sql, args = _to_qmark_and_args(query, params, ordered_param_names)

            logger.debug("[DB] SQL:\n%s", qmark_sql)
            logger.debug("[DB] ARGS: %s", args)

            cursor.execute(qmark_sql, args)
            # autocommit=True; if you disable it, call self.connection.commit()
            rows_affected = cursor.rowcount
            return rows_affected

        except Exception as e:
            # if autocommit=False, do a rollback
            logger.error(f"Execution error: {e}", exc_info=True)
            raise
        finally:
            if cursor is not None:
                cursor.close()

    def get_session(self):
        """Return self for compatibility"""
        return self

    def close(self):
        """Close connection"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("SQL Server connection closed")
            finally:
                self.connection = None