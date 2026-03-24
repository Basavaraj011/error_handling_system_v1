#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import subprocess
import signal
import time
import json
import re
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

print("run.py | Workspace root:", WORKSPACE_ROOT)
SCRIPTS_DIR = os.path.join(WORKSPACE_ROOT, "scripts")

from database.database_operations import update_processed_errors
from connections.database_connections import DatabaseManager
from config.settings import DATABASE_URL

LOG = logging.getLogger("runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)

def py() -> str:
    """Current Python executable (handles venvs & Windows)."""
    return sys.executable or "python"

def _script_path(file_name: str) -> str:
    return os.path.join(SCRIPTS_DIR, file_name)

def run_script(file_name: str, extra_env=None, extra_args=None) -> int:
    """
    Execute a script from scripts/ as a separate (blocking) process.
    Returns the process exit code.
    """
    path = _script_path(file_name)
    if not os.path.exists(path):
        LOG.error("Script not found: %s", path)
        return 127

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    cmd = [py(), path] + (extra_args or [])
    LOG.info("Running: %s", " ".join(cmd))
    return subprocess.call(cmd, env=env)

def start_script_background(file_name: str, extra_env=None, extra_args=None) -> subprocess.Popen:
    """
    Start a script from scripts/ in the background and return the Popen handle.
    """
    path = _script_path(file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Script not found: {path}")

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    cmd = [py(), path] + (extra_args or [])
    LOG.info("Starting (bg): %s", " ".join(cmd))
    # text=True for readable stdout if needed later
    return subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# ---- single commands ----

def cmd_extract() -> int:
    return run_script("run_error_extractor.py")

def cmd_ticket() -> int:
    return run_script("run_jira_ticketing.py")

def cmd_selfheal() -> int:
    return run_script("run_self_heal.py")    

def _spawn_ngrok_http(port: int) -> subprocess.Popen:
    """
    Start ngrok http <port>. Returns the process handle.
    Raises FileNotFoundError if ngrok is not on PATH.
    """
    cmd = ["ngrok", "http", str(port)]
    LOG.info("Starting ngrok: %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        return proc
    except FileNotFoundError:
        LOG.error("ngrok not found on PATH. Install and/or add to PATH, then retry.")
        raise

def _try_get_ngrok_url_from_api(timeout_sec: float = 20.0) -> str | None:
    """
    Poll ngrok local API for tunnels and return the first https public_url.
    """
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = Request("http://127.0.0.1:4040/api/tunnels", headers={"Accept": "application/json"})
            with urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tunnels = data.get("tunnels") or []
            for t in tunnels:
                url = t.get("public_url") or ""
                if url.startswith("https://"):
                    return url
        except (URLError, HTTPError, json.JSONDecodeError):
            pass
        time.sleep(0.3)
    return None

def _try_get_ngrok_url_from_stdout(proc: subprocess.Popen, timeout_sec: float = 20.0) -> str | None:
    """
    Fallback: parse ngrok stdout lines to find https URL if API not ready.
    """
    # Read non-blocking-ish for a limited time
    start = time.time()
    pattern = re.compile(r"https://[a-zA-Z0-9\-\._]+\.ngrok[-\w]*\.app")
    # Some versions emit ...ngrok-free.app or other domains; also match generic https URLs
    generic = re.compile(r"https://[^\s]+")

    while time.time() - start < timeout_sec:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            time.sleep(0.2)
            continue
        lower = line.strip().lower()
        if "forwarding" in lower or "url=" in lower or "started tunnel" in lower:
            m = pattern.search(line) or generic.search(line)
            if m:
                return m.group(0)
    return None

def _start_webhook_and_ngrok(port: int) -> tuple[subprocess.Popen, subprocess.Popen, str | None]:
    """
    Start webhook in background and ngrok for the given port.
    Returns (webhook_proc, ngrok_proc, public_url)
    """
    # 1) Start webhook (bg)
    webhook_env = {"PORT": str(port)}
    webhook_proc = start_script_background("run_outgoing_webhook.py", extra_env=webhook_env)

    # Give the Flask app a moment to bind
    time.sleep(1.5)

    # 2) Start ngrok
    ngrok_proc = _spawn_ngrok_http(port)

    # 3) Discover public URL
    url = _try_get_ngrok_url_from_api(timeout_sec=20.0)
    if not url:
        url = _try_get_ngrok_url_from_stdout(ngrok_proc, timeout_sec=20.0)

    return webhook_proc, ngrok_proc, url

def _wait_forever_and_cleanup(webhook_proc: subprocess.Popen, ngrok_proc: subprocess.Popen | None = None):
    """
    Wait on webhook process, relay Ctrl+C to clean up children.
    """
    def _terminate(proc: subprocess.Popen | None, name: str):
        if proc and proc.poll() is None:
            LOG.info("Stopping %s (pid=%s)...", name, proc.pid)
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

    try:
        # Stream webhook stdout to console for visibility
        if webhook_proc.stdout:
            LOG.info("Streaming webhook logs (Ctrl+C to stop)...")
        while True:
            # Forward webhook logs if available
            if webhook_proc.stdout:
                line = webhook_proc.stdout.readline()
                if line:
                    sys.stdout.write("[webhook] " + line)
                    sys.stdout.flush()
            # Exit if webhook died
            if webhook_proc.poll() is not None:
                LOG.warning("Webhook process exited with code %s", webhook_proc.returncode)
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        LOG.info("Interrupted by user.")
    finally:
        _terminate(ngrok_proc, "ngrok")
        _terminate(webhook_proc, "webhook")

def cmd_webhook(port: int | None, with_ngrok: bool) -> int:
    port = port or 3978
    if with_ngrok:
        try:
            webhook_proc, ngrok_proc, url = _start_webhook_and_ngrok(port)
        except FileNotFoundError:
            return 127

        teams_url = (url + "/teams/outgoing") if url else None
        if teams_url:
            print("\n" + "=" * 80)
            print("Teams outgoing webhook URL (paste this in Teams):")
            print(f"  {teams_url}")
            print("=" * 80 + "\n")
        else:
            LOG.warning("Could not determine ngrok public URL. Check ngrok output and 4040 API.")

        _wait_forever_and_cleanup(webhook_proc, ngrok_proc)
        # If we reach here, webhook exited — return its code if available
        return webhook_proc.returncode if webhook_proc.returncode is not None else 0
    else:
        # Blocking mode: just run the webhook normally (no ngrok)
        env = {"PORT": str(port)} if port else None
        return run_script("run_outgoing_webhook.py", extra_env=env)

# ---- pipeline ----

def cmd_pipeline(skip_extract=False, skip_ticket=False, skip_webhook=False, skip_selfheal = False,
                 webhook_port: int | None = None, with_ngrok: bool = False) -> int:
    if not skip_extract:
        rc = cmd_extract()
        if rc != 0:
            return rc

    if not skip_ticket:
        rc = cmd_ticket()
        if rc != 0:
            return rc
        
    if not skip_selfheal:
        rc = cmd_selfheal()
        if rc != 0:
            return rc

    if skip_webhook:
        return 0

    # Webhook is the last step. If with_ngrok, keep it running with tunnel.
    return cmd_webhook(port=webhook_port or 3978, with_ngrok=with_ngrok)

# ---- args ----

def build_arg_parser():
    p = argparse.ArgumentParser(
        description="Runner for extractor, ticketing, and webhook with optional ngrok."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("extract", help="Run error extractor (scripts/run_error_extractor.py)")
    sub.add_parser("ticket", help="Run Jira ticketing (scripts/run_jira_ticketing.py)")
    sub.add_parser("selfheal", help="Run Selfheal (scripts/run_self_heal.py)")

    p_webhook = sub.add_parser("webhook", help="Run Teams outgoing webhook")
    p_webhook.add_argument("--port", type=int, help="Port for webhook (via PORT env var). Default 3978.")
    p_webhook.add_argument("--with-ngrok", action="store_true", help="Also start ngrok http <port> and print public URL.")

    p_pipe = sub.add_parser("pipeline", help="Run extraction -> ticketing -> webhook sequentially")
    p_pipe.add_argument("--skip-extract", action="store_true", help="Skip the extract step")
    p_pipe.add_argument("--skip-ticket", action="store_true", help="Skip the ticket step")
    p_pipe.add_argument("--skip-webhook", action="store_true", help="Skip the webhook step")
    p_pipe.add_argument("--webhook-port", type=int, help="Port for webhook (PORT env var). Default 3978.")
    p_pipe.add_argument("--with-ngrok", action="store_true", help="Start ngrok for webhook and print public URL.")

    return p

def main():
    args = build_arg_parser().parse_args()

    if args.cmd == "extract":
        sys.exit(cmd_extract())

    if args.cmd == "ticket":
        sys.exit(cmd_ticket())

    if args.cmd == "selfheal":
        sys.exit(cmd_selfheal())

    if args.cmd == "webhook":
        sys.exit(cmd_webhook(port=args.port, with_ngrok=args.with_ngrok))

    if args.cmd == "pipeline":
        sys.exit(cmd_pipeline(
            skip_extract=args.skip_extract,
            skip_ticket=args.skip_ticket,
            skip_webhook=args.skip_webhook,
            webhook_port=args.webhook_port,
            with_ngrok=args.with_ngrok
        ))
    
    db_manager = DatabaseManager(DATABASE_URL)
    
    update_processed_errors(db_manager)

if __name__ == "__main__":
    main()