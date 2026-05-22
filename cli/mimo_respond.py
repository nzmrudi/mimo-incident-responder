"""
MiMo DevOps Incident Responder — CLI
=====================================

Pipe any error log / stack trace into this tool and MiMo will:
  • Identify the root cause
  • Classify severity
  • Suggest concrete fix steps
  • Output a remediation snippet (if applicable)

Usage:
  cat /var/log/myapp.log | mimo-respond
  journalctl -u nginx -n 100 | mimo-respond --severity high
  mimo-respond --file error.log --json
  mimo-respond --watch /var/log/syslog        # live mode
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx

# ---------- Config ----------
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://platform.xiaomimimo.com/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
HISTORY_DIR = Path.home() / ".mimo-responder" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ANSI colors for terminal output
class C:
    R = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


SEVERITY_COLORS = {
    "critical": C.RED + C.BOLD,
    "high": C.RED,
    "medium": C.YELLOW,
    "low": C.BLUE,
    "info": C.GREEN,
}

SYSTEM_PROMPT = """You are MiMo Incident Responder, an expert SRE / DevOps engineer.
You analyze error logs, stack traces, and crash dumps to identify root causes
and prescribe fixes.

You MUST respond with valid JSON in this exact schema:
{
  "severity": "critical" | "high" | "medium" | "low" | "info",
  "category": "<short tag, e.g. database, network, auth, oom, disk, config>",
  "summary": "<one-sentence root cause in plain language>",
  "root_cause": "<2-4 sentence technical explanation>",
  "fix_steps": ["<step 1>", "<step 2>", ...],
  "remediation_snippet": "<optional: bash/code snippet that fixes it, or null>",
  "prevention": "<one-sentence preventive measure>",
  "confidence": 0.0-1.0
}

Be precise. Cite specific lines/error codes from the log. If the log is benign
or contains no error, return severity="info" and explain that.
"""


def call_mimo(log_text: str, hint: Optional[str] = None) -> dict:
    if not MIMO_API_KEY:
        return demo_response(log_text)

    user = log_text.strip()
    if hint:
        user = f"# Operator hint\n{hint}\n\n# Log\n{log_text.strip()}"

    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1200,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=60) as cli:
        r = cli.post(
            f"{MIMO_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {MIMO_API_KEY}"},
            json=payload,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)


def demo_response(log_text: str) -> dict:
    """Offline demo response when MIMO_API_KEY is not set."""
    lower = log_text.lower()
    if "out of memory" in lower or "oom" in lower or "killed" in lower:
        return {
            "severity": "critical",
            "category": "oom",
            "summary": "Process killed by OOM killer due to memory exhaustion",
            "root_cause": (
                "The kernel OOM killer terminated the process because system "
                "memory was exhausted. This is typically caused by a memory "
                "leak, undersized container limits, or sudden traffic spike."
            ),
            "fix_steps": [
                "Check current memory usage: free -h",
                "Identify top consumers: ps aux --sort=-%mem | head",
                "Increase container/cgroup memory limit",
                "Restart the affected service",
                "Add a memory monitor / alert",
            ],
            "remediation_snippet": (
                "# Increase systemd unit memory limit\n"
                "systemctl set-property myapp.service MemoryMax=4G\n"
                "systemctl restart myapp.service"
            ),
            "prevention": "Set MemoryHigh + MemoryMax limits and add Prometheus alert at 80% RSS.",
            "confidence": 0.85,
        }
    if "connection refused" in lower or "econnrefused" in lower:
        return {
            "severity": "high",
            "category": "network",
            "summary": "Upstream service unreachable — connection refused",
            "root_cause": (
                "The client attempted to connect to a service that is either "
                "not listening on the expected port, has crashed, or is "
                "blocked by a firewall."
            ),
            "fix_steps": [
                "Verify the upstream service is running",
                "Check the listening port: ss -tlnp | grep <port>",
                "Test connectivity: curl -v <host>:<port>",
                "Inspect firewall rules: iptables -L -n",
                "Restart the upstream if needed",
            ],
            "remediation_snippet": "systemctl status <service> && systemctl restart <service>",
            "prevention": "Add a healthcheck + circuit breaker on the client side.",
            "confidence": 0.78,
        }
    return {
        "severity": "info",
        "category": "demo",
        "summary": "[DEMO MODE] Set MIMO_API_KEY env var for real MiMo analysis",
        "root_cause": "This is a stub response shown when no API key is configured.",
        "fix_steps": [
            "export MIMO_API_KEY=<your-key>",
            "Get a key at https://platform.xiaomimimo.com",
        ],
        "remediation_snippet": None,
        "prevention": "Always configure MIMO_API_KEY in production.",
        "confidence": 1.0,
    }


def render_pretty(result: dict, log_preview: str):
    sev = result.get("severity", "info").lower()
    color = SEVERITY_COLORS.get(sev, C.GREEN)

    print()
    print(f"{C.BOLD}{C.MAGENTA}╭─ MiMo Incident Responder ─────────────────────────╮{C.R}")
    print(f"{C.DIM}  Model: {MIMO_MODEL}   Time: {datetime.now().isoformat(timespec='seconds')}{C.R}")
    print()

    print(f"  {color}● {sev.upper()}{C.R}  {C.DIM}({result.get('category','?')}){C.R}   "
          f"{C.DIM}confidence {result.get('confidence',0):.0%}{C.R}")
    print()

    print(f"  {C.BOLD}Summary:{C.R}")
    print(f"    {result.get('summary','-')}")
    print()

    print(f"  {C.BOLD}Root Cause:{C.R}")
    for line in (result.get("root_cause", "") or "").split("\n"):
        print(f"    {line}")
    print()

    print(f"  {C.BOLD}{C.CYAN}Fix Steps:{C.R}")
    for i, step in enumerate(result.get("fix_steps", []), 1):
        print(f"    {C.CYAN}{i}.{C.R} {step}")
    print()

    snip = result.get("remediation_snippet")
    if snip:
        print(f"  {C.BOLD}{C.GREEN}Remediation Snippet:{C.R}")
        for line in snip.split("\n"):
            print(f"    {C.GREEN}│{C.R} {line}")
        print()

    print(f"  {C.BOLD}{C.YELLOW}Prevention:{C.R}")
    print(f"    {result.get('prevention','-')}")

    print()
    print(f"{C.BOLD}{C.MAGENTA}╰────────────────────────────────────────────────────╯{C.R}")
    print()


def save_history(log_text: str, result: dict):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = HISTORY_DIR / f"{ts}-{result.get('severity','info')}.json"
    path.write_text(json.dumps({
        "ts": datetime.now().isoformat(),
        "model": MIMO_MODEL,
        "log_preview": log_text[:2000],
        "result": result,
    }, indent=2, ensure_ascii=False))
    return path


def cmd_analyze(args):
    if args.file:
        log_text = Path(args.file).read_text(errors="replace")
    elif not sys.stdin.isatty():
        log_text = sys.stdin.read()
    else:
        print(f"{C.RED}No input. Pipe a log or use --file.{C.R}", file=sys.stderr)
        sys.exit(1)

    if not log_text.strip():
        print(f"{C.YELLOW}Empty input{C.R}", file=sys.stderr)
        sys.exit(1)

    result = call_mimo(log_text, hint=args.hint)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        render_pretty(result, log_text[:200])

    if not args.no_save:
        path = save_history(log_text, result)
        if not args.json:
            print(f"{C.DIM}saved → {path}{C.R}")


def cmd_history(args):
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)[: args.limit]
    if not files:
        print(f"{C.DIM}No history yet.{C.R}")
        return
    for f in files:
        d = json.loads(f.read_text())
        sev = d["result"].get("severity", "info")
        color = SEVERITY_COLORS.get(sev, C.GREEN)
        print(f"  {color}● {sev:8}{C.R}  {d['ts'][:19]}  {d['result'].get('summary','-')[:80]}")


def cmd_watch(args):
    print(f"{C.DIM}Watching {args.path}... (Ctrl-C to stop){C.R}")
    path = Path(args.path)
    if not path.exists():
        print(f"{C.RED}File not found: {path}{C.R}")
        sys.exit(1)

    last_size = path.stat().st_size
    buffer = []
    error_keywords = ("error", "fail", "fatal", "exception", "traceback", "panic", "killed")

    try:
        while True:
            time.sleep(2)
            cur_size = path.stat().st_size
            if cur_size > last_size:
                with path.open("r", errors="replace") as f:
                    f.seek(last_size)
                    new_lines = f.read().splitlines()
                last_size = cur_size

                for line in new_lines:
                    buffer.append(line)
                    if len(buffer) > 50:
                        buffer.pop(0)
                    if any(k in line.lower() for k in error_keywords):
                        chunk = "\n".join(buffer[-30:])
                        print(f"\n{C.YELLOW}[!] Error pattern detected — analyzing...{C.R}")
                        result = call_mimo(chunk)
                        render_pretty(result, chunk[:200])
                        save_history(chunk, result)
                        buffer.clear()
    except KeyboardInterrupt:
        print(f"\n{C.DIM}Stopped.{C.R}")


def main():
    parser = argparse.ArgumentParser(
        prog="mimo-respond",
        description="AI-powered incident response, powered by Xiaomi MiMo",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_an = sub.add_parser("analyze", help="Analyze a log (default)")
    p_an.add_argument("--file", "-f", help="Read log from file")
    p_an.add_argument("--hint", "-H", help="Operator hint to guide analysis")
    p_an.add_argument("--json", action="store_true", help="Output raw JSON")
    p_an.add_argument("--no-save", action="store_true", help="Skip history save")
    p_an.set_defaults(func=cmd_analyze)

    p_hi = sub.add_parser("history", help="Show recent incidents")
    p_hi.add_argument("--limit", "-n", type=int, default=20)
    p_hi.set_defaults(func=cmd_history)

    p_wa = sub.add_parser("watch", help="Tail a log and alert on errors")
    p_wa.add_argument("path", help="Path to log file")
    p_wa.set_defaults(func=cmd_watch)

    # If no subcommand given, treat as 'analyze' with passthrough args
    raw = sys.argv[1:]
    known_subs = {"analyze", "history", "watch", "-h", "--help"}
    if not raw or raw[0] not in known_subs:
        raw = ["analyze"] + raw
    args = parser.parse_args(raw)
    args.func(args)


if __name__ == "__main__":
    main()
