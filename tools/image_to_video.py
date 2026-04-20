"""
Convert static avatar PNG → looping 5-second MP4 for MuseTalk.

MuseTalk needs a reference video, not a still image.
This creates a 5-second 30fps loop from each avatar PNG — the pipeline
will extend or trim it to match audio length automatically.

Run:  python tools/image_to_video.py

Output: avatars/older_man.mp4, avatars/woman.mp4, avatars/younger_man.mp4

Requires: ffmpeg on PATH
"""

import subprocess
import sys
from pathlib import Path

AVATARS = [
    "older_man",
    "woman",
    "younger_man",
]

DURATION = 5    # seconds
FPS      = 30
SIZE     = "512:512"
AVATARS_DIR = Path("avatars")


def image_to_video(name: str) -> None:
    src = AVATARS_DIR / f"{name}.png"
    dst = AVATARS_DIR / f"{name}.mp4"

    if not src.exists():
        print(f"  SKIP {src} — not found. Run create_placeholder_avatars.py first.")
        return

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(src),
        "-t", str(DURATION),
        "-vf", f"scale={SIZE},format=yuv420p",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        str(dst),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR {name}: {result.stderr[-300:]}", file=sys.stderr)
    else:
        print(f"  Created: {dst}")


if __name__ == "__main__":
    print("Converting avatar PNGs to looping MP4s …")
    for avatar in AVATARS:
        image_to_video(avatar)
    print("\nDone. avatars/*.mp4 are ready for MuseTalk.")
