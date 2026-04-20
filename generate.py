"""
Avatar Pipeline — batch runner.

Usage:
  # Run the 5 sample exercises (for testing)
  python generate.py --exercises samples/sample_exercises.json

  # Run only Part 1, first 10 exercises
  python generate.py --exercises content/part1/part1_topics.json --limit 10

  # Full Part 1 batch
  python generate.py --exercises content/part1/part1_topics.json

  # Skip R2 upload and DB update (local dry-run)
  python generate.py --exercises samples/sample_exercises.json --no-upload

Flags:
  --exercises  PATH   JSON file of exercises to process (required)
  --limit      N      Stop after N exercises (default: all)
  --no-upload         Skip R2 upload and DB update
  --backend    NAME   Override LIPSYNC_BACKEND (musetalk | sadtalker)
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ── logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/pipeline.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

# ── lazy imports (so the app is importable before deps are installed) ─────────

def _load_pipeline(backend: str | None):
    from pipeline.tts import TTSEngine
    from pipeline.lipsync import LipSyncEngine
    from pipeline.encode import VideoEncoder
    from pipeline.upload import R2Uploader
    from pipeline.db import ExerciseDB

    return (
        TTSEngine(),
        LipSyncEngine(backend=backend),
        VideoEncoder(),
        R2Uploader(),
        ExerciseDB(),
    )


# ── exercise helpers ──────────────────────────────────────────────────────────

def flatten_exercises(raw: list[dict]) -> list[dict]:
    """
    Convert content JSON entries into flat exercise records.

    Part 1 / Part 3: one video per question  (4–5 questions per topic set)
    Part 2:          one video per cue card  (the full prompt read-out)
    """
    exercises = []

    for entry in raw:
        part = entry.get("part")

        if part == 2:
            # Single video: examiner reads the cue card prompt
            bullets = "; ".join(entry["bullet_points"])
            text = (
                f"Now I'm going to give you a topic. "
                f"{entry['prompt']} "
                f"You should say: {bullets}. "
                f"You have one minute to prepare, then speak for one to two minutes."
            )
            exercises.append({
                "id": entry["id"],
                "part": part,
                "avatar": entry["avatar"],
                "text": text,
            })

        else:
            # One video per question (Part 1 and Part 3)
            for i, question in enumerate(entry["questions"]):
                exercises.append({
                    "id": f"{entry['id']}_q{i + 1}",
                    "part": part,
                    "avatar": entry["avatar"],
                    "text": question,
                })

    return exercises


def load_exercises(path: str | Path) -> list[dict]:
    """
    Load exercises from a JSON file.
    Handles both:
      - content/* JSON (topic/cue card format) — auto-flattened
      - samples/*.json (already flat, with 'text' field)
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data:
        return []

    # Already flat if first entry has a 'text' key
    if "text" in data[0]:
        return data

    return flatten_exercises(data)


# ── pipeline ──────────────────────────────────────────────────────────────────

def process_exercise(
    exercise: dict,
    tts,
    lipsync,
    encoder,
    uploader,
    db,
    no_upload: bool,
) -> str | None:
    """
    Run one exercise through the full pipeline.
    Returns the public R2 URL on success, None on failure.
    """
    eid = exercise["id"]
    work_dir = Path("output") / "temp" / eid
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. TTS
        audio = tts.generate(exercise["text"], work_dir / "audio.wav")

        # 2. Lip-sync
        raw_video = lipsync.generate(audio, exercise["avatar"], work_dir / "raw.mp4")

        # 3. Encode to final 720p MP4
        final_video = encoder.encode(raw_video, work_dir / "final.mp4")

        if no_upload:
            log.info("[no-upload] %s → %s", eid, final_video)
            return str(final_video)

        # 4. Upload to R2
        key = uploader.make_key(eid, exercise["part"])
        url = uploader.upload(final_video, key)

        # 5. Update Supabase
        db.update_video_url(eid, url)

        return url

    except Exception as exc:
        log.error("FAILED %s: %s", eid, exc)
        _log_error(eid, str(exc))
        return None

    finally:
        # Clean up temp files to save disk space during large batches
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def _log_error(exercise_id: str, message: str) -> None:
    Path("output").mkdir(exist_ok=True)
    with open("output/errors.log", "a", encoding="utf-8") as f:
        f.write(f"{exercise_id}\t{message}\n")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Avatar pipeline batch runner")
    parser.add_argument("--exercises", required=True, help="Path to exercises JSON")
    parser.add_argument("--limit", type=int, default=None, help="Max exercises to process")
    parser.add_argument("--no-upload", action="store_true", help="Skip R2 upload and DB update")
    parser.add_argument("--backend", default=None, help="Lipsync backend override")
    args = parser.parse_args()

    Path("output").mkdir(exist_ok=True)

    exercises = load_exercises(args.exercises)
    if args.limit:
        exercises = exercises[: args.limit]

    log.info("Loaded %d exercises from %s", len(exercises), args.exercises)

    tts, lipsync, encoder, uploader, db = _load_pipeline(args.backend)

    ok = 0
    fail = 0

    for exercise in tqdm(exercises, desc="Generating", unit="video"):
        url = process_exercise(exercise, tts, lipsync, encoder, uploader, db, args.no_upload)
        if url:
            ok += 1
        else:
            fail += 1

    log.info("Done — %d succeeded, %d failed", ok, fail)
    if fail:
        log.warning("See output/errors.log for details.")


if __name__ == "__main__":
    main()
