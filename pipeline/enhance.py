"""
Face enhancement — GFPGAN.

Used as a ONE-TIME pre-processing step on source avatar images, not on every
output video (frame-by-frame enhancement would be prohibitively slow at scale).

Install:  pip install gfpgan
Model:    Download GFPGANv1.4.pth and set GFPGAN_MODEL_PATH in .env.
          https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth
"""

import logging
import os
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


class FaceEnhancer:
    def __init__(self, model_path: str | Path | None = None):
        from gfpgan import GFPGANer  # lazy import

        model_path = Path(model_path or os.getenv("GFPGAN_MODEL_PATH", "deps/GFPGANv1.4.pth"))
        if not model_path.exists():
            raise FileNotFoundError(
                f"GFPGAN model not found: {model_path}\n"
                "Download GFPGANv1.4.pth and set GFPGAN_MODEL_PATH in .env."
            )

        self.enhancer = GFPGANer(
            model_path=str(model_path),
            upscale=1,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=None,
        )
        log.info("GFPGAN loaded from %s", model_path)

    def enhance_image(self, input_path: str | Path, output_path: str | Path) -> Path:
        """
        Enhance faces in a single image (PNG/JPG).
        Call this once per avatar source photo before running the batch.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not read image: {input_path}")

        _, _, enhanced = self.enhancer.enhance(
            img, has_aligned=False, only_center_face=False, paste_back=True
        )

        cv2.imwrite(str(output_path), enhanced)
        log.info("Enhanced %s → %s", input_path, output_path)
        return output_path

    def enhance_all_avatars(self, avatars_dir: str | Path = "avatars") -> None:
        """
        Enhance all PNG/JPG source images in avatars_dir.
        Writes enhanced versions alongside originals (_enhanced suffix).
        """
        avatars_dir = Path(avatars_dir)
        for src in sorted(avatars_dir.glob("*.png")) + sorted(avatars_dir.glob("*.jpg")):
            if "_enhanced" in src.stem:
                continue
            out = src.with_stem(src.stem + "_enhanced")
            self.enhance_image(src, out)
