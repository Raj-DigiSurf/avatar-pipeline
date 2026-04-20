"""
Video encoding — ffmpeg.

Encodes raw lip-sync output to final 720p H.264 / AAC MP4 suitable for
browser playback and R2 hosting.

Requires: ffmpeg on PATH  (or set FFMPEG_PATH in .env)
"""

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

FFMPEG = os.getenv("FFMPEG_PATH", "ffmpeg")


class VideoEncoder:
    def __init__(self):
        self.width = int(os.getenv("OUTPUT_WIDTH", "1280"))
        self.height = int(os.getenv("OUTPUT_HEIGHT", "720"))
        self.fps = int(os.getenv("OUTPUT_FPS", "30"))

    def encode(self, input_path: str | Path, output_path: str | Path) -> Path:
        """
        Re-encode `input_path` to 720p H.264 / AAC MP4 at `output_path`.
        Returns the resolved output path.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                   f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(self.fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        log.debug("ffmpeg cmd: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (exit {result.returncode}):\n{result.stderr}")

        log.debug("Encoded → %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)
        return output_path
