"""
TTS wrapper — XTTS-v2 (production) or pyttsx3 (local testing).

Production (RunPod):
  pip install TTS
  Uses XTTS-v2 — natural, accented English voice (~2 GB model, GPU recommended)

Local testing (no GPU):
  pip install pyttsx3
  Uses Windows/macOS built-in TTS — basic quality, instant, no model download
  Pass use_local=True or set TTS_ENGINE=local in .env
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


class TTSEngine:
    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, use_local: bool = False):
        self.use_local = use_local or os.getenv("TTS_ENGINE", "").lower() == "local"

        if self.use_local:
            import pyttsx3 as _pyttsx3
            self._pyttsx3 = _pyttsx3
            # Probe voice ID once; reinit engine per generate() call to avoid COM hang
            _e = _pyttsx3.init()
            voices = _e.getProperty("voices")
            en_voices = [v for v in voices if "en" in v.id.lower()]
            self._voice_id = en_voices[0].id if en_voices else None
            _e.stop()
            del _e
            log.info("TTS engine: pyttsx3 (local, no GPU)")
        else:
            import torch
            from TTS.api import TTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            log.info("Loading XTTS-v2 on %s ...", device)
            self._tts = TTS(self.MODEL_NAME).to(device)
            log.info("XTTS-v2 ready.")

    VOICE_MAP = {
        "australian_woman": "avatars/voices/australian_woman.wav",
        "uk_woman":         "avatars/voices/uk_woman.wav",
        "older_man":        "avatars/voices/older_man.wav",
        "younger_man":      "avatars/voices/younger_man.wav",
        "woman":            "avatars/voices/australian_woman.wav",
    }
    DEFAULT_VOICE = "avatars/voices/default.wav"

    def generate(self, text: str, output_path: str | Path,
                 language: str = "en", avatar: str | None = None) -> Path:
        """Synthesise text to a WAV file. Returns the output path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.use_local:
            engine = self._pyttsx3.init()
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)
            engine.setProperty("rate", 150)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            engine.stop()
        else:
            speaker_wav = self.VOICE_MAP.get(avatar or "", self.DEFAULT_VOICE)
            if not Path(speaker_wav).exists():
                speaker_wav = self.DEFAULT_VOICE
            self._tts.tts_to_file(
                text=text,
                file_path=str(output_path),
                language=language,
                speaker_wav=speaker_wav,
            )

        log.debug("TTS -> %s", output_path)
        return output_path
