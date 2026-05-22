"""
MiMo DevOps Incident Responder — Web Dashboard
================================================
View incident history with filtering and full report drill-down.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import os
import sys
from datetime import datetime
from typing import Optional

# Reuse the CLI logic
sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
from mimo_respond import call_mimo, save_history, HISTORY_DIR, MIMO_MODEL  # noqa

app = FastAPI(title="MiMo Incident Responder", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AnalyzeRequest(BaseModel):
    log: str
    hint: Optional[str] = None


@app.get("/api/health")
def health():
    return {"ok": True, "model": MIMO_MODEL}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not req.log.strip():
        raise HTTPException(400, "Empty log")
    try:
        result = call_mimo(req.log, hint=req.hint)
    except Exception as e:
        raise HTTPException(502, f"MiMo error: {e}")
    save_history(req.log, result)
    return {"result": result, "ts": datetime.utcnow().isoformat()}


@app.get("/api/history")
def history(limit: int = 50):
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)[:limit]
    out = []
    for f in files:
        try:
            d = json.loads(f.read_text())
            out.append({
                "id": f.stem,
                "ts": d["ts"],
                "severity": d["result"].get("severity", "info"),
                "category": d["result"].get("category", "?"),
                "summary": d["result"].get("summary", ""),
                "confidence": d["result"].get("confidence", 0),
            })
        except Exception:
            continue
    return {"items": out, "total": len(out)}


@app.get("/api/incident/{incident_id}")
def incident(incident_id: str):
    f = HISTORY_DIR / f"{incident_id}.json"
    if not f.exists():
        raise HTTPException(404, "Not found")
    return json.loads(f.read_text())


@app.get("/api/stats")
def stats():
    files = list(HISTORY_DIR.glob("*.json"))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    categories: dict = {}
    for f in files:
        try:
            d = json.loads(f.read_text())
            sev = d["result"].get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
            cat = d["result"].get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1
        except Exception:
            pass
    return {
        "total": len(files),
        "by_severity": counts,
        "by_category": dict(sorted(categories.items(), key=lambda x: -x[1])[:10]),
    }


# --- static frontend ---
WEB_DIR = Path(__file__).parent
INDEX = WEB_DIR / "index.html"


@app.get("/")
def root():
    return FileResponse(INDEX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=False)
