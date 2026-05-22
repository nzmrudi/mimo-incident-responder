# MiMo Incident Responder 🚨🤖

> **AI-powered SRE / DevOps incident response, built on Xiaomi MiMo**
>
> Submission for **Xiaomi MiMo Orbit 100T Token Creator Incentive Program**

![Status](https://img.shields.io/badge/status-live-22c55e) ![MiMo](https://img.shields.io/badge/powered%20by-Xiaomi%20MiMo-ff6900) ![License](https://img.shields.io/badge/license-MIT-blue)

---

## 🎯 What is this?

**MiMo Incident Responder** turns your error logs into actionable fixes. Pipe a stack trace, journalctl output, or kubelet log into the CLI — MiMo reads it, reasons about the root cause, classifies severity, and returns a structured incident report with remediation steps and prevention advice.

Two surfaces:
- **CLI tool** (`mimo-respond`) — pipe-friendly, JSON output, watch mode for live tailing
- **Web dashboard** — paste/upload logs, drill into past incidents, severity stats

```bash
$ journalctl -u myapp -n 200 | mimo-respond

╭─ MiMo Incident Responder ─────────────────────────╮
  ● CRITICAL  (oom)   confidence 85%

  Summary:
    Process killed by OOM killer due to memory exhaustion

  Root Cause:
    The kernel OOM killer terminated gunicorn worker (pid:5678)
    because system memory was exhausted. Connection pool to Postgres
    was exhausted in parallel, suggesting either a connection leak
    or a sudden traffic spike.

  Fix Steps:
    1. Check current memory usage: free -h
    2. Identify top consumers: ps aux --sort=-%mem | head
    3. Increase systemd unit memory limit
    4. Restart gunicorn with reduced worker count
    5. Audit DB connection pool config (close on context exit)
    ...
╰────────────────────────────────────────────────────╯
```

---

## ✨ Features

| | |
|---|---|
| 🧠 **Structured incident reports** | severity, category, root cause, fix steps, snippet, prevention — every field machine-readable JSON |
| 🚀 **Pipe-friendly CLI** | `cat err.log \| mimo-respond` — works with any source: journalctl, docker logs, kubectl logs, tail |
| 👀 **Watch mode** | `mimo-respond watch /var/log/syslog` — auto-trigger on error keywords, alert on detection |
| 📊 **Web dashboard** | Severity KPIs, full history, click-through to drill into any past incident |
| 🎯 **Hint support** | `--hint "happens during deploy"` to give MiMo extra context |
| 💾 **Persistent history** | All analyses saved as JSON in `~/.mimo-responder/history/` |
| 🌐 **Multilingual** | MiMo answers in the operator's language — IDR/EN/ZH out of the box |
| 🔌 **OpenAI-compatible** | Drop-in MiMo endpoint, no SDK lock-in |

---

## 🏗️ Architecture

```
┌──────────────────────┐
│  Log source          │   journalctl, kubectl, tail, paste, upload
│  (any text stream)   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  CLI / FastAPI       │   parse, attach hint, route
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Xiaomi MiMo API     │   mimo-v2.5-pro · response_format=json_object
│  (reasoning engine)  │
└──────────┬───────────┘
           │  structured JSON
           ▼
┌──────────────────────┐
│  Renderer +          │   pretty CLI · web dashboard · history file
│  history store       │
└──────────────────────┘
```

The whole product is ~250 LoC of Python + a single-file dashboard. The heavy lifting — log triage, root-cause reasoning, fix authoring — is delegated to MiMo. We bias the output via a strict system prompt and `response_format=json_object` so every reply slots cleanly into the renderer.

---

## 🚀 Setup

### Local
```bash
git clone https://github.com/<you>/mimo-incident-responder.git
cd mimo-incident-responder
pip install -r web/requirements.txt
export MIMO_API_KEY=<your-key>      # from platform.xiaomimimo.com
```

### CLI
```bash
# from a pipe
journalctl -u nginx -n 100 | python cli/mimo_respond.py

# from a file
python cli/mimo_respond.py --file samples/db-pool-oom.log

# raw JSON for another tool
docker logs myapp 2>&1 | python cli/mimo_respond.py --json | jq

# watch mode
python cli/mimo_respond.py watch /var/log/syslog

# history
python cli/mimo_respond.py history -n 20
```

### Web dashboard
```bash
cd web && python server.py
# open http://localhost:8001
```

---

## 🧪 Sample logs

The `samples/` directory contains real-world failure modes to try the analyzer on:

| File | Failure mode |
|---|---|
| `db-pool-oom.log` | Postgres pool exhaustion → gunicorn OOM-killed |
| `nginx-upstream.log` | nginx upstream connection refused + SSL handshake fail |
| `k8s-gpu-pod.log` | k8s pod failing on GPU device + image pull 401 |

```bash
python cli/mimo_respond.py --file samples/db-pool-oom.log
```

---

## 🌍 Why MiMo?

We picked **Xiaomi MiMo** for incident response specifically because:

1. **Strong reasoning on noisy text** — log files are messy; MiMo handles partial context, multiple intermixed events, and stack traces well.
2. **Fast on structured-output tasks** — `response_format=json_object` is honored, low jitter on the schema.
3. **Multilingual operators** — same dashboard works for the SG/CN/ID team without fine-tuning.
4. **Cost** — analytics calls are frequent (one per error spike); MiMo's pricing keeps this sustainable.
5. **OpenAI-compatible API** — zero SDK migration cost.

---

## 📂 Project Structure
```
mimo-incident-responder/
├── cli/
│   └── mimo_respond.py        # CLI entry point + core logic
├── web/
│   ├── server.py              # FastAPI app
│   ├── index.html             # dashboard SPA
│   └── requirements.txt
├── samples/                   # real-world failure logs
│   ├── db-pool-oom.log
│   ├── nginx-upstream.log
│   └── k8s-gpu-pod.log
├── docs/
└── README.md
```

---

## 🛣️ Roadmap

- [ ] Slack / Discord / Telegram notifier on critical incidents
- [ ] Prometheus alertmanager webhook → automatic MiMo triage
- [ ] Trend detection: "this incident has happened N times this week"
- [ ] MiMo function-calling: let MiMo execute the remediation snippet (with confirm)
- [ ] Vector index of past incidents for similarity lookup before calling MiMo

---

## 📜 License

MIT

---

## 🙏 Built with

- **[Xiaomi MiMo](https://platform.xiaomimimo.com/)** — the reasoning engine
- **FastAPI**, **httpx**, vanilla HTML/JS — the plumbing

For the **Xiaomi MiMo Orbit 100T Creator Incentive Program** ✨
