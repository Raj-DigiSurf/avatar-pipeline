"""
Avatar Pipeline — local batch management UI.

Run:  python ui/app.py
Open: http://localhost:5000
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, Response

app = Flask(__name__)

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content"
SAMPLES_DIR = ROOT / "samples"
OUTPUT_LOG  = ROOT / "output" / "pipeline.log"
ERRORS_LOG  = ROOT / "output" / "errors.log"

# Active process reference (one batch at a time)
_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()


# ── Content stats ──────────────────────────────────────────────────────────────

def get_content_stats() -> dict:
    stats = {}
    files = {
        "part1": CONTENT_DIR / "part1" / "part1_topics.json",
        "part2": CONTENT_DIR / "part2" / "part2_cuecards.json",
        "part3": CONTENT_DIR / "part3" / "part3_discussion.json",
    }
    for key, path in files.items():
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if key == "part2":
                stats[key] = {"topics": len(data), "videos": len(data)}
            else:
                q_count = sum(len(e.get("questions", [])) for e in data)
                stats[key] = {"topics": len(data), "videos": q_count}
        else:
            stats[key] = {"topics": 0, "videos": 0}
    stats["total"] = sum(v["videos"] for v in stats.values())
    return stats


def get_avatar_status() -> dict:
    avatars_dir = ROOT / "avatars"
    personas = ["older_man", "woman", "younger_man"]
    status = {}
    for p in personas:
        png = (avatars_dir / f"{p}.png").exists()
        mp4 = (avatars_dir / f"{p}.mp4").exists()
        status[p] = {"png": png, "mp4": mp4, "ready": png and mp4}
    return status


def get_exercise_files() -> list[dict]:
    files = []
    for path in sorted(CONTENT_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        label = path.stem.replace("_", " ").title()
        files.append({
            "path": str(path.relative_to(ROOT)),
            "label": label,
            "count": len(data),
        })
    for path in sorted(SAMPLES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        files.append({
            "path": str(path.relative_to(ROOT)),
            "label": f"[SAMPLE] {path.stem}",
            "count": len(data),
        })
    return files


def is_running() -> bool:
    with _proc_lock:
        return _proc is not None and _proc.poll() is None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        content_stats  = get_content_stats(),
        avatar_status  = get_avatar_status(),
        exercise_files = get_exercise_files(),
        running        = is_running(),
    )


@app.route("/api/status")
def api_status():
    return jsonify({
        "running":       is_running(),
        "avatar_status": get_avatar_status(),
        "content_stats": get_content_stats(),
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    global _proc

    if is_running():
        return jsonify({"error": "A batch is already running."}), 409

    body      = request.get_json(force=True)
    exercises = body.get("exercises")
    limit     = body.get("limit")
    no_upload = body.get("no_upload", False)
    backend   = body.get("backend")

    if not exercises:
        return jsonify({"error": "exercises path required"}), 400

    cmd = [sys.executable, str(ROOT / "generate.py"), "--exercises", exercises]
    if limit:
        cmd += ["--limit", str(limit)]
    if no_upload:
        cmd += ["--no-upload"]
    if backend:
        cmd += ["--backend", backend]

    (ROOT / "output").mkdir(exist_ok=True)
    log_file = open(OUTPUT_LOG, "a")

    with _proc_lock:
        _proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    return jsonify({"started": True, "pid": _proc.pid, "cmd": " ".join(cmd)})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _proc
    with _proc_lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            return jsonify({"stopped": True})
    return jsonify({"stopped": False, "reason": "No active process."})


@app.route("/api/log")
def api_log():
    lines = int(request.args.get("lines", 100))
    if OUTPUT_LOG.exists():
        all_lines = OUTPUT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        return jsonify({"lines": all_lines[-lines:]})
    return jsonify({"lines": []})


@app.route("/api/errors")
def api_errors():
    if ERRORS_LOG.exists():
        rows = []
        for line in ERRORS_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t", 1)
            rows.append({"id": parts[0], "error": parts[1] if len(parts) > 1 else ""})
        return jsonify({"errors": rows})
    return jsonify({"errors": []})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
