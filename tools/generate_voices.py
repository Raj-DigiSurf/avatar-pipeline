"""
Generate reference voice WAVs for XTTS-v2 voice cloning.

Uses edge-tts (free Microsoft Azure TTS, no API key needed) to create
~15-second reference clips for each avatar persona, then converts to WAV.

Run:  python tools/generate_voices.py

Output:
  avatars/voices/older_man.wav
  avatars/voices/australian_woman.wav
  avatars/voices/uk_woman.wav
  avatars/voices/younger_man.wav
  avatars/voices/default.wav  (copy of older_man)

Requires: pip install edge-tts
          ffmpeg on PATH
"""

import asyncio
import subprocess
import shutil
from pathlib import Path

# ── Voice mapping: avatar → edge-tts voice name ─────────────────────────────
# Full list: edge-tts --list-voices
VOICES = {
    "older_man": {
        "voice": "en-GB-RyanNeural",        # British male, mature
        "text": (
            "Good morning. Welcome to the speaking test. "
            "My name is David and I will be your examiner today. "
            "In part one, I will ask you some general questions about yourself "
            "and a range of familiar topics. Let us begin with your hometown. "
            "Can you tell me about the place where you grew up? "
            "What do you enjoy most about living there?"
        ),
    },
    "australian_woman": {
        "voice": "en-AU-NatashaNeural",      # Australian female
        "text": (
            "Hello there. I am going to give you a topic and I would like you "
            "to talk about it for one to two minutes. Before you start, "
            "you will have one minute to think about what you want to say. "
            "You can make some notes if you wish. Here is your topic card. "
            "Please describe a memorable journey you have taken. "
            "You should say where you went and when."
        ),
    },
    "uk_woman": {
        "voice": "en-GB-SoniaNeural",        # British female
        "text": (
            "Right, let us move on to part three of the test. "
            "I would like to discuss some more general questions related to "
            "the topic we have been talking about. First of all, "
            "do you think travel broadens the mind? In what ways can "
            "travelling to different countries change a person's perspective? "
            "Some people say international tourism does more harm than good."
        ),
    },
    "younger_man": {
        "voice": "en-US-GuyNeural",          # American male, younger
        "text": (
            "Welcome to the discussion section. Now I would like to ask you "
            "some questions about education and technology. How has technology "
            "changed the way students learn today compared to the past? "
            "Do you think online learning can replace traditional classroom "
            "teaching? What are the advantages and disadvantages of using "
            "artificial intelligence in education?"
        ),
    },
}

VOICES_DIR = Path("avatars/voices")


async def generate_voice(name: str, voice: str, text: str) -> Path:
    """Generate MP3 via edge-tts, then convert to WAV."""
    import edge_tts

    mp3_path = VOICES_DIR / f"{name}.mp3"
    wav_path = VOICES_DIR / f"{name}.wav"

    print(f"  Generating {name} ({voice})...")
    communicate = edge_tts.Communicate(text, voice, rate="-10%")
    await communicate.save(str(mp3_path))

    # Convert MP3 → WAV (16kHz mono — what XTTS-v2 expects)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(mp3_path),
        "-ar", "22050",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {name}: {result.stderr[-300:]}")

    mp3_path.unlink()  # cleanup MP3
    print(f"  ✓ {wav_path} ({wav_path.stat().st_size / 1024:.0f} KB)")
    return wav_path


async def main():
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating reference voice WAVs for XTTS-v2...\n")

    for name, config in VOICES.items():
        await generate_voice(name, config["voice"], config["text"])

    # Default voice = older_man (primary examiner)
    default = VOICES_DIR / "default.wav"
    shutil.copy2(VOICES_DIR / "older_man.wav", default)
    print(f"  ✓ {default} (copy of older_man)")

    print(f"\nDone. {len(VOICES) + 1} voice files in {VOICES_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
