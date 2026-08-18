#!/usr/bin/python3
"""External watchdog for Hermes Gateway file-descriptor exhaustion on macOS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

LABEL = "ai.hermes.gateway"
WATCHDOG_LABEL = "ai.hermes.gateway-fd-watchdog"
DEFAULT_THRESHOLD = 180
DEFAULT_COOLDOWN = 300


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()


def launchctl_target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


def gateway_pid() -> int | None:
    result = subprocess.run(
        ["/bin/launchctl", "print", launchctl_target()],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    match = re.search(r"^\s*pid\s*=\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def open_file_count(pid: int) -> int | None:
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-p", str(pid)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode not in (0, 1):
        return None
    lines = result.stdout.splitlines()
    return max(0, len(lines) - 1) if lines else 0


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)


def append_event(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1_000_000:
        rotated = path.with_suffix(path.suffix + ".1")
        rotated.unlink(missing_ok=True)
        path.replace(rotated)
    with path.open("a") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = hermes_home()
    state_dir = home / "health"
    state_path = state_dir / "gateway-fd-watchdog.json"
    event_log = home / "logs" / "gateway-fd-watchdog.log"
    lock_dir = state_dir / ".gateway-fd-watchdog.lock"
    now = int(time.time())

    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        lock_dir.mkdir()
    except FileExistsError:
        return 0

    try:
        pid = gateway_pid()
        count = open_file_count(pid) if pid else None
        payload = {
            "checked_at": now,
            "pid": pid,
            "open_files": count,
            "threshold": args.threshold,
            "action": "healthy",
        }

        if pid is None:
            payload["action"] = "gateway_not_running"
            atomic_json(state_path, payload)
            return 0
        if count is None:
            payload["action"] = "count_failed"
            atomic_json(state_path, payload)
            append_event(event_log, payload)
            return 1
        if count < args.threshold:
            atomic_json(state_path, payload)
            return 0

        previous = {}
        if state_path.exists():
            try:
                previous = json.loads(state_path.read_text())
            except (OSError, json.JSONDecodeError):
                previous = {}
        last_restart = int(previous.get("restarted_at") or 0)
        if now - last_restart < args.cooldown:
            payload["action"] = "cooldown"
            payload["restarted_at"] = last_restart
            atomic_json(state_path, payload)
            return 0

        if args.dry_run:
            payload["action"] = "would_restart"
            atomic_json(state_path, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 2

        old_pid = pid
        result = subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", launchctl_target()],
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload["action"] = "restart_requested"
        payload["old_pid"] = old_pid
        payload["restarted_at"] = now
        payload["launchctl_returncode"] = result.returncode
        if result.stderr.strip():
            payload["launchctl_error"] = result.stderr.strip()[:500]

        new_pid = None
        new_count = None
        deadline = time.time() + 30
        while time.time() < deadline:
            time.sleep(1)
            candidate = gateway_pid()
            if candidate and candidate != old_pid:
                new_pid = candidate
                new_count = open_file_count(candidate)
                break
        payload["new_pid"] = new_pid
        payload["new_open_files"] = new_count
        payload["action"] = (
            "restarted" if result.returncode == 0 and new_pid else "restart_failed"
        )
        atomic_json(state_path, payload)
        append_event(event_log, payload)
        return 0 if payload["action"] == "restarted" else 1
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
