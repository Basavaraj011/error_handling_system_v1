import json
from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LearningEngine:
    """
    Learns over time from:
    - past successful patches
    - rejected PR patches
    - reviewer comments
    - human-applied fixes
    - confidence outcomes

    Produces context packs used by SolutionGenerator.
    """

    def __init__(self):
        self.db = DatabaseManager(DATABASE_URL)

    # ==========================================================
    #  FETCH CONTEXT (history)
    # ==========================================================
    def fetch_context(self, error_hash: str, lang: str):
        """
        Returns structured knowledge to improve future generations.
        Includes:
        - previous patches for same error hash
        - similar errors with successful solutions
        - reviewer comments from PRs
        - human-modified corrections from rejected fixes
        """

        try:
            rows = self.db.fetch_all("""
                SELECT error_hash, language, patch, reviewer_notes,
                       human_fix, confidence, status
                FROM SelfHeal_History
                WHERE error_hash = ? OR language = ?
                ORDER BY created_at DESC
                LIMIT 10
            """, (error_hash, lang))
        except Exception as e:
            logger.error(f"[LearningEngine] DB error: {e}")
            return None

        context = []
        for r in rows:
            context.append({
                "patch": r["patch"],
                "reviewer_notes": r["reviewer_notes"],
                "human_fix": r["human_fix"],
                "status": r["status"],
                "confidence": r["confidence"],
            })

        logger.info(f"[LearningEngine] Loaded {len(context)} historical entries.")
        return context

    # ==========================================================
    #  RECORD OUTCOME
    # ==========================================================
    def record_outcome(self, error_hash, file_path, lang, confidence, applied_patch):
        """
        Stores patch outcome for future learning.
        Actual acceptance/rejection updated later via PR process.
        """

        try:
            pass
            # self.db.execute("""
            #     INSERT INTO SelfHeal_History
            #     (error_hash, file_path, language, patch, confidence, status)
            #     VALUES (?, ?, ?, ?, ?, ?)
            # """, (error_hash, file_path, lang, applied_patch, confidence, "pending"))
        except Exception as e:
            logger.error(f"[LearningEngine] Failed to store history: {e}")