"""
TTS wrapper — XTTS-v2 via Coqui TTS.

Install:  pip install TTS
Model:    tts_models/multilingual/multi-dataset/xtts_v2
          Downloads automatically on first use (~2 GB).
"""

import logging
import torch
from pathlib import Path

log = logging.getLogger(__name__)


class TTSEngine:
    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self):
        from TTS.api import TTS  # imported here so the rest of the app works without TTS installed

        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("Loading XTTS-v2 on %s …", device)
        self.tts = TTS(self.MODEL_NAME).to(device)
        log.info("XTTS-v2 ready.")

    def generate(self, text: str, output_path: str | Path, language: str = "en") -> Path:
        """
        Synthesise `text` to a WAV file at `output_path`.
        Returns the resolved output path.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.tts.tts_to_file(
            text=text,
            file_path=str(output_path),
            language=language,
        )
        log.debug("TTS → %s", output_path)
        return output_path
