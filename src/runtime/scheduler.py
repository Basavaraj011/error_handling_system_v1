# src/runtime/scheduler.py
"""
Lightweight scheduler that triggers one Phase-1 run for all enabled teams every N seconds.
Defaults to 300s (5 minutes), configurable via SCHED_INTERVAL_SECONDS.
"""

from __future__ import annotations
import os
import time
import signal
import random
import logging
from datetime import datetime

# ❗adjust if package root differs (e.g., remove '' if you run from repo root)
from scripts.run import main as run_once

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# --- Graceful shutdown flag ---
_SHOULD_STOP = False


def _handle_stop(signum, frame):
    global _SHOULD_STOP
    logger.info(f"Received signal {signum}; will stop after current tick.")
    _SHOULD_STOP = True


def start_scheduler() -> None:
    """
    Starts a loop that runs `scripts.run_all.main()` every interval seconds.
    Resilient to errors: logs and continues on exceptions.
    """
    # Base interval (seconds). Default = 300 (5 minutes)
    try:
        interval = int(os.getenv("SCHED_INTERVAL_SECONDS", "300"))
    except ValueError:
        interval = 300

    # Optional jitter (seconds) to avoid synchronized starts across multiple instances
    # Set SCHED_START_JITTER=0 to disable
    try:
        start_jitter = int(os.getenv("SCHED_START_JITTER", "10"))
    except ValueError:
        start_jitter = 10

    if start_jitter > 0:
        jitter = random.randint(0, max(0, start_jitter))
        logger.info(f"Applying start jitter of {jitter}s before first tick")
        time.sleep(jitter)

    logger.info(f"Starting scheduler with interval={interval}s")

    # Hook signals for graceful shutdown
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    while not _SHOULD_STOP:
        tick_start_iso = datetime.utcnow().isoformat()
        logger.info(f"[TICK START] {tick_start_iso}")

        try:
            # Run a single pass for all enabled teams
            run_once()
        except Exception as e:
            # Never crash the scheduler loop on unhandled exceptions
            logger.exception(f"Scheduler tick failed: {e}")

        if _SHOULD_STOP:
            break

        logger.info(f"[TICK END] Sleeping for {interval}s\n")
        # Sleep in small steps to react faster to shutdown signals
        slept = 0
        step = min(1, interval)  # 1s steps
        while slept < interval and not _SHOULD_STOP:
            time.sleep(step)
            slept += step

    logger.info("Scheduler stopped gracefully.")


if __name__ == "__main__":
    start_scheduler()