"""
Avatar Pipeline — batch runner.

Usage:
  # Test 5 samples locally (no GPU — skips lipsync, tests TTS + R2 + Supabase)
  python generate.py --exercises samples/sample_exercises.json --skip-lipsync

  # Full test on RunPod (real lipsync)
  python generate.py --exercises samples/sample_exercises.json

  # Dry run — no upload, no DB (useful for checking TTS output only)
  python generate.py --exercises samples/sample_exercises.json --no-upload

  # Full Part 1 batch
  python generate.py --exercises content/part1/part1_topics.json

  # Full Part 1 batch, first 10 only
  python generate.py --exercises content/part1/part1_topics.json --limit 10

Flags:
  --exercises    PATH   JSON file of exercises to process (required)
  --limit        N      Stop after N exercises (default: all)
  --skip-lipsync        Skip MuseTalk — overlay audio on static avatar video.
                        Use this to test TTS + encode + R2 + Supabase without GPU.
  --local-tts           Use pyttsx3 (built-in OS TTS) instead of XTTS-v2.
                        Combine with --skip-lipsync for a full local test with no GPU/models.
  --no-upload           Skip R2 upload and DB update entirely (outputs stay local)
  --backend      NAME   Override LIPSYNC_BACKEND env var (musetalk | sadtalker)
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ── logging ───────────────────────────────────────────────────────────────────

Path("output").mkdir(exist_ok=True)

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

# ── ffmpeg helper (used by skip-lipsync mode) ─────────────────────────────────

def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


# ── pipeline loader ───────────────────────────────────────────────────────────

def _load_pipeline(backend: str | None, skip_lipsync: bool, no_upload: bool, local_tts: bool):
    from pipeline.tts import TTSEngine
    from pipeline.encode import VideoEncoder

    tts     = TTSEngine(use_local=local_tts)
    encoder = VideoEncoder()
    lipsync = None
    uploader = None
    db       = None

    if not skip_lipsync:
        from pipeline.lipsync import LipSyncEngine
        lipsync = LipSyncEngine(backend=backend)

    if not no_upload:
        from pipeline.upload import R2Uploader
        from pipeline.db import ExerciseDB
        uploader = R2Uploader()
        db       = ExerciseDB()

    return tts, lipsync, encoder, uploader, db


# ── exercise helpers ──────────────────────────────────────────────────────────

def flatten_exercises(raw: list[dict]) -> list[dict]:
    """
    Convert content JSON entries into flat exercise records.

    Part 1 / Part 3 : one video per question  (4–5 questions per topic set)
    Part 2           : one video per cue card  (the full prompt read-out)
    """
    exercises = []
    for entry in raw:
        part = entry.get("part")
        if part == 2:
            bullets = "; ".join(entry["bullet_points"])
            text = (
                f"Now I'm going to give you a topic. "
                f"{entry['prompt']} "
                f"You should say: {bullets}. "
                f"You have one minute to prepare, then speak for one to two minutes."
            )
            exercises.append({"id": entry["id"], "part": part,
                               "avatar": entry["avatar"], "text": text})
        else:
            for i, question in enumerate(entry["questions"]):
                exercises.append({"id": f"{entry['id']}_q{i + 1}", "part": part,
                                   "avatar": entry["avatar"], "text": question})
    return exercises


def load_exercises(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data:
        return []
    return data if "text" in data[0] else flatten_exercises(data)


# ── skip-lipsync helper ───────────────────────────────────────────────────────

AVATAR_TO_FILE = {
    "older_man":        "avatars/older_man.mp4",
    "australian_woman": "avatars/australian_woman.mp4",
    "uk_woman":         "avatars/uk_woman.mp4",
    "younger_man":      "avatars/younger_man.mp4",
    "woman":            "avatars/australian_woman.mp4",
}

def _static_video(audio_path: Path, avatar_key: str, output_path: Path) -> Path:
    """
    Overlay TTS audio onto the looping avatar MP4 (no lip-sync).
    Used when --skip-lipsync is set.
    """
    avatar_mp4 = Path(AVATAR_TO_FILE.get(avatar_key, f"avatars/{avatar_key}.mp4"))
    if not avatar_mp4.exists():
        raise FileNotFoundError(f"Avatar MP4 not found: {avatar_mp4}")

    ffmpeg = _get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-stream_loop", "-1", "-i", str(avatar_mp4),   # loop avatar video
        "-i", str(audio_path),                          # TTS audio
        "-shortest",                                    # trim to audio length
        "-c:v", "copy",
        "-c:a", "aac",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg static-video failed:\n{result.stderr}")
    return output_path


# ── per-exercise pipeline ─────────────────────────────────────────────────────

def process_exercise(
    exercise: dict,
    tts,
    lipsync,
    encoder,
    uploader,
    db,
    skip_lipsync: bool,
    no_upload: bool,
) -> str | None:
    eid      = exercise["id"]
    work_dir = Path("output") / "temp" / eid
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. TTS
        audio = tts.generate(exercise["text"], work_dir / "audio.wav", avatar=exercise.get("avatar"))

        # 2. Lipsync (or static fallback)
        if skip_lipsync:
            raw_video = _static_video(audio, exercise["avatar"], work_dir / "raw.mp4")
            log.info("[skip-lipsync] %s — static avatar + TTS audio", eid)
        else:
            raw_video = lipsync.generate(audio, exercise["avatar"], work_dir / "raw.mp4")

        # 3. Encode to 720p MP4
        final_video = encoder.encode(raw_video, work_dir / "final.mp4")

        if no_upload:
            # Copy to output/local/ so it persists after cleanup
            local_out = Path("output") / "local" / f"{eid}.mp4"
            local_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_video, local_out)
            log.info("[no-upload] saved locally -> %s", local_out)
            return str(local_out)

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
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def _log_error(exercise_id: str, message: str) -> None:
    with open("output/errors.log", "a", encoding="utf-8") as f:
        f.write(f"{exercise_id}\t{message}\n")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Avatar pipeline batch runner")
    parser.add_argument("--exercises",    required=True,        help="Path to exercises JSON")
    parser.add_argument("--limit",        type=int, default=None, help="Max exercises to process")
    parser.add_argument("--skip-lipsync", action="store_true",  help="Skip MuseTalk, use static avatar + audio")
    parser.add_argument("--local-tts",    action="store_true",  help="Use pyttsx3 instead of XTTS-v2")
    parser.add_argument("--no-upload",    action="store_true",  help="Skip R2 upload and DB update")
    parser.add_argument("--backend",      default=None,         help="Lipsync backend override")
    args = parser.parse_args()

    exercises = load_exercises(args.exercises)
    if args.limit:
        exercises = exercises[: args.limit]

    log.info("Loaded %d exercises | skip-lipsync=%s | local-tts=%s | no-upload=%s",
             len(exercises), args.skip_lipsync, args.local_tts, args.no_upload)

    tts, lipsync, encoder, uploader, db = _load_pipeline(
        args.backend, args.skip_lipsync, args.no_upload, args.local_tts
    )

    ok = fail = 0
    for exercise in tqdm(exercises, desc="Generating", unit="video"):
        result = process_exercise(
            exercise, tts, lipsync, encoder, uploader, db,
            args.skip_lipsync, args.no_upload,
        )
        if result:
            ok += 1
        else:
            fail += 1

    log.info("Done — %d succeeded, %d failed", ok, fail)
    if fail:
        log.warning("See output/errors.log for details.")
    if args.no_upload:
        log.info("Videos saved to output/local/")


if __name__ == "__main__":
    main()
