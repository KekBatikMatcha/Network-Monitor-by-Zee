#!/usr/bin/env python3
"""
Z • Net Monitor (monitor.py)
- Reads config.json
- Pings targets on an interval
- Writes:
    data/status.json     (latest snapshot for PHP dashboard)
    data/history.jsonl   (append-only log)
    data/alerts.jsonl    (status-change events)
- Optional Telegram alerting with cooldown

For authorized networks only.
"""

import json
import os
import time
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CONFIG = {
    "interval_seconds": 3,
    "timeout_ms": 1200,
    "degraded_ms": 120,
    "fail_threshold": 2,
    "targets": [
        {"name": "Google DNS", "host": "8.8.8.8"},
        {"name": "Cloudflare DNS", "host": "1.1.1.1"},
        {"name": "Router", "host": "192.168.1.1"}
    ],
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "cooldown_seconds": 60
    }
}

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
STATUS_PATH = os.path.join(DATA_DIR, "status.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.jsonl")
ALERTS_PATH = os.path.join(DATA_DIR, "alerts.jsonl")
STATE_PATH = os.path.join(DATA_DIR, "state.json")  # internal (persists failures/prev status)


# -------------------------- Helpers --------------------------

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def clamp_int(x: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(x)
        return max(lo, min(hi, v))
    except Exception:
        return default

def telegram_send(bot_token: str, chat_id: str, text: str) -> None:
    """Best-effort Telegram notify (no crash on failure)."""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# -------------------------- Ping Implementation --------------------------

def ping(host: str, timeout_ms: int) -> Tuple[bool, Optional[float], str]:
    """
    Returns (ok, latency_ms, raw_output)
    Uses system ping for Windows/Linux/macOS.
    """
    system = platform.system().lower()
    timeout_ms = max(200, int(timeout_ms))

    if "windows" in system:
        # -n 1 : one echo request
        # -w timeout(ms)
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        # Linux/macOS:
        # -c 1 : one ping
        # -W timeout(seconds) on Linux; macOS uses -W in ms? It's inconsistent.
        # We'll use -c 1 and rely on subprocess timeout as a safety net.
        cmd = ["ping", "-c", "1", host]

    try:
        # Give subprocess a small extra window over timeout_ms
        hard_timeout = max(1.0, (timeout_ms / 1000.0) + 1.0)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=hard_timeout)
        out = (res.stdout or "") + (res.stderr or "")
        ok = (res.returncode == 0)

        latency = parse_latency_ms(out, system)
        # If ping says ok but we can't parse latency, still treat as ok.
        return ok, latency, out.strip()
    except subprocess.TimeoutExpired:
        return False, None, "timeout"
    except FileNotFoundError:
        return False, None, "ping not found"
    except Exception as e:
        return False, None, f"error: {e}"

def parse_latency_ms(output: str, system: str) -> Optional[float]:
    """
    Extract latency from ping output (best-effort).
    Windows often: "time=23ms" or "time<1ms"
    Linux/mac: "time=23.4 ms"
    """
    s = output.lower()

    # quick common patterns
    # handle time<1ms
    if "time<" in s and "ms" in s:
        return 1.0

    # find "time=" then parse float until "ms"
    idx = s.find("time=")
    if idx != -1:
        tail = s[idx + 5:]
        # tail might start with "23ms" or "23.4 ms"
        num = ""
        for ch in tail:
            if ch.isdigit() or ch == ".":
                num += ch
            else:
                if num:
                    break
        try:
            return float(num) if num else None
        except Exception:
            return None

    # some windows locales might show "time:" instead of "time="
    idx = s.find("time:")
    if idx != -1:
        tail = s[idx + 5:]
        num = ""
        for ch in tail:
            if ch.isdigit() or ch == ".":
                num += ch
            else:
                if num:
                    break
        try:
            return float(num) if num else None
        except Exception:
            return None

    return None


# -------------------------- Status Logic --------------------------

def classify_status(ok: bool, latency_ms: Optional[float], degraded_ms: int) -> str:
    if not ok:
        return "DOWN"
    if latency_ms is None:
        return "UP"
    return "DEGRADED" if latency_ms >= degraded_ms else "UP"

def normalize_targets(cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    targets = cfg.get("targets", [])
    if not isinstance(targets, list):
        return []
    out = []
    for t in targets:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name", "")).strip() or str(t.get("host", "")).strip()
        host = str(t.get("host", "")).strip()
        if not host:
            continue
        out.append({"name": name, "host": host})
    return out


# -------------------------- Main Loop --------------------------

def main() -> None:
    ensure_dirs()

    cfg = load_json(CONFIG_PATH, DEFAULT_CONFIG)
    if not isinstance(cfg, dict):
        cfg = DEFAULT_CONFIG

    interval = clamp_int(cfg.get("interval_seconds"), 1, 3600, DEFAULT_CONFIG["interval_seconds"])
    timeout_ms = clamp_int(cfg.get("timeout_ms"), 200, 10000, DEFAULT_CONFIG["timeout_ms"])
    degraded_ms = clamp_int(cfg.get("degraded_ms"), 1, 20000, DEFAULT_CONFIG["degraded_ms"])
    fail_threshold = clamp_int(cfg.get("fail_threshold"), 1, 20, DEFAULT_CONFIG["fail_threshold"])

    tg = cfg.get("telegram", {})
    if not isinstance(tg, dict):
        tg = DEFAULT_CONFIG["telegram"]

    tg_enabled = bool(tg.get("enabled", False))
    tg_token = str(tg.get("bot_token", "")).strip()
    tg_chat = str(tg.get("chat_id", "")).strip()
    tg_cooldown = clamp_int(tg.get("cooldown_seconds"), 5, 3600, 60)

    targets = normalize_targets(cfg)
    if not targets:
        print("No targets found in config.json. Add targets and run again.")
        return

    # Load persistent state
    state = load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}

    print(f"[Z Net Monitor] Started. interval={interval}s timeout={timeout_ms}ms targets={len(targets)}")
    print(f"[Z Net Monitor] Writing: {STATUS_PATH}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            now_iso = iso_now()

            snapshot_by_host: Dict[str, Dict[str, Any]] = {}

            for t in targets:
                name = t["name"]
                host = t["host"]

                prev = state.get(host, {})
                if not isinstance(prev, dict):
                    prev = {}

                prev_status = str(prev.get("status", "UNKNOWN"))
                failures = int(prev.get("failures", 0) or 0)
                last_alert_ts = float(prev.get("last_alert_ts", 0) or 0)

                ok, latency, raw = ping(host, timeout_ms)
                current_status = classify_status(ok, latency, degraded_ms)

                # update failures
                if ok:
                    failures = 0
                    last_seen = now_iso
                else:
                    failures += 1
                    last_seen = prev.get("last_seen", None)

                # only mark DOWN if consecutive failures >= threshold
                # (helps avoid flapping)
                effective_status = current_status
                if current_status == "DOWN" and failures < fail_threshold:
                    # treat as DEGRADED during early fails (optional)
                    effective_status = "DEGRADED" if latency is None else "DEGRADED"

                # status change alert (based on effective_status)
                if effective_status != prev_status and prev_status != "UNKNOWN":
                    alert_obj = {
                        "ts": now_iso,
                        "name": name,
                        "host": host,
                        "from": prev_status,
                        "to": effective_status
                    }
                    append_jsonl(ALERTS_PATH, alert_obj)

                    # telegram notify (rate-limited per-host)
                    now_ts = time.time()
                    if tg_enabled and tg_token and tg_chat and (now_ts - last_alert_ts) >= tg_cooldown:
                        msg = f"[Z Net Monitor] {name} ({host}) {prev_status} -> {effective_status}"
                        telegram_send(tg_token, tg_chat, msg)
                        last_alert_ts = now_ts

                item = {
                    "name": name,
                    "host": host,
                    "status": effective_status,
                    "last_latency_ms": latency,
                    "failures": failures,
                    "last_seen": last_seen if ok else (last_seen if last_seen else None),
                    "updated_at": now_iso
                }

                snapshot_by_host[host] = item

                # Write history line (always)
                append_jsonl(HISTORY_PATH, item)

                # Update state
                state[host] = {
                    "status": effective_status,
                    "failures": failures,
                    "last_seen": item["last_seen"],
                    "last_alert_ts": last_alert_ts
                }

            # Write snapshot + state atomically
            atomic_write_json(STATUS_PATH, snapshot_by_host)
            atomic_write_json(STATE_PATH, state)

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[Z Net Monitor] Stopped.")


if __name__ == "__main__":
    main()
