"""
Lip-sync wrapper — MuseTalk (primary) / SadTalker (fallback).

MuseTalk:
  git clone https://github.com/TMElyralab/MuseTalk deps/MuseTalk
  cd deps/MuseTalk && pip install -r requirements.txt
  Set MUSETALK_DIR in .env

SadTalker:
  git clone https://github.com/OpenTalker/SadTalker deps/SadTalker
  cd deps/SadTalker && pip install -r requirements.txt
  Set SADTALKER_DIR in .env

Avatar source:
  Each persona needs a short looping reference video (2–5 s, 30 fps, 512x512+).
  Place at avatars/older_man.mp4, avatars/australian_woman.mp4,
  avatars/uk_woman.mp4, avatars/younger_man.mp4.
  The avatar video is looped automatically to match audio length.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

AVATAR_MAP = {
    "older_man":          "avatars/older_man.mp4",
    "australian_woman":   "avatars/australian_woman.mp4",
    "uk_woman":           "avatars/uk_woman.mp4",
    "younger_man":        "avatars/younger_man.mp4",
    # legacy alias
    "woman":              "avatars/australian_woman.mp4",
}


class LipSyncEngine:
    def __init__(self, backend: str | None = None):
        self.backend = (backend or os.getenv("LIPSYNC_BACKEND", "musetalk")).lower()
        self.musetalk_dir = Path(os.getenv("MUSETALK_DIR", "deps/MuseTalk"))
        self.sadtalker_dir = Path(os.getenv("SADTALKER_DIR", "deps/SadTalker"))
        log.info("LipSyncEngine backend: %s", self.backend)

    def generate(
        self,
        audio_path: str | Path,
        avatar_key: str,
        output_path: str | Path,
    ) -> Path:
        """
        Generate a lip-synced video.

        Args:
            audio_path:  Path to the TTS-generated WAV file.
            avatar_key:  One of 'older_man', 'woman', 'younger_man'.
            output_path: Where to write the output MP4.

        Returns:
            Resolved output path.
        """
        audio_path = Path(audio_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        avatar_video = Path(AVATAR_MAP[avatar_key])
        if not avatar_video.exists():
            raise FileNotFoundError(
                f"Avatar video not found: {avatar_video}\n"
                "Place a short looping MP4 at that path before running the pipeline."
            )

        if self.backend == "musetalk":
            return self._run_musetalk(audio_path, avatar_video, output_path)
        elif self.backend == "sadtalker":
            return self._run_sadtalker(audio_path, avatar_video, output_path)
        else:
            raise ValueError(f"Unknown lipsync backend: {self.backend!r}")

    # ── MuseTalk ──────────────────────────────────────────────────────

    def _run_musetalk(self, audio: Path, avatar: Path, output: Path) -> Path:
        script = (self.musetalk_dir / "scripts" / "inference.py").resolve()
        task_name = output.stem
        result_dir = tempfile.mkdtemp(prefix="musetalk_")

        config = {
            task_name: {
                "video_path": str(avatar.resolve()),
                "audio_path": str(audio.resolve()),
                "bbox_shift": 0,
            }
        }
        config_path = Path(result_dir) / "cfg.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))

        cmd = [
            os.getenv("PYTHON_BIN", "python3"), str(script),
            "--inference_config", str(config_path),
            "--result_dir", result_dir,
            "--output_vid_name", task_name,
            "--fps", str(os.getenv("OUTPUT_FPS", "30")),
            "--version", "v15",
        ]
        try:
            self._run(cmd, cwd=self.musetalk_dir, label="MuseTalk")
            generated = Path(result_dir) / "v15" / f"{task_name}.mp4"
            if not generated.exists():
                raise FileNotFoundError(
                    f"MuseTalk did not produce output for {task_name}"
                )
            shutil.move(str(generated), str(output))
        finally:
            shutil.rmtree(result_dir, ignore_errors=True)
        return output

    # ── SadTalker ─────────────────────────────────────────────────────

    def _run_sadtalker(self, audio: Path, avatar: Path, output: Path) -> Path:
        script = (self.sadtalker_dir / "inference.py").resolve()
        cmd = [
            os.getenv("PYTHON_BIN", "python3"), str(script),
            "--driven_audio", str(audio.resolve()),
            "--source_image", str(avatar.resolve()),
            "--result_dir", str(output.parent.resolve()),
            "--still",
            "--preprocess", "full",
            "--enhancer", "gfpgan",
        ]
        self._run(cmd, cwd=self.sadtalker_dir, label="SadTalker")
        # SadTalker writes its own filename — find and rename to output
        generated = next(output.parent.glob("*.mp4"))
        generated.rename(output)
        return output

    # ── shared ────────────────────────────────────────────────────────

    @staticmethod
    def _run(cmd: list, cwd: Path, label: str) -> None:
        log.debug("%s cmd: %s", label, " ".join(cmd))
        env = {**os.environ, "PYTHONPATH": str(cwd)}
        result = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed (exit {result.returncode}):\n{result.stderr}")
        log.debug("%s stdout: %s", label, result.stdout[-500:])
