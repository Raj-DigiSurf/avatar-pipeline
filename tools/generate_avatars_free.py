"""
Generate photorealistic avatar images via Pollinations.ai (free, no API key).
Uses SDXL under the hood. No GPU required — runs anywhere.

Run:  python tools/generate_avatars_free.py

Generates 4 variants per persona so you can pick the best one.
Output: avatars/variants/  +  avatars/australian_woman.png, avatars/uk_woman.png
"""

import time
import urllib.parse
from pathlib import Path
import requests

OUT_DIR = Path("avatars")
VAR_DIR = OUT_DIR / "variants"
OUT_DIR.mkdir(exist_ok=True)
VAR_DIR.mkdir(exist_ok=True)

BASE_URL = "https://image.pollinations.ai/prompt/{prompt}"

PERSONAS = [
    {
        "filename": "australian_woman.png",
        "label":    "Australian Woman Examiner",
        "prompt": (
            "professional studio headshot portrait of a beautiful 35 year old Australian woman, "
            "IELTS examiner, warm smile, wearing a dark navy blazer, white blouse, "
            "straight blonde or light brown hair, natural makeup, looking directly at camera, "
            "plain light grey studio background, sharp focus, professional studio lighting, "
            "photorealistic, high quality, 8k"
        ),
        "negative": (
            "sunglasses, glasses, cartoon, illustration, blurry, watermark, text, "
            "casual clothing, outdoor background, deformed face, extra limbs"
        ),
    },
    {
        "filename": "uk_woman.png",
        "label":    "UK Woman Examiner",
        "prompt": (
            "professional studio headshot portrait of a beautiful 38 year old British woman, "
            "IELTS examiner, composed professional expression, wearing a charcoal blazer, "
            "pearl blouse, chestnut or dark hair neatly styled, natural makeup, "
            "looking directly at camera, plain light grey studio background, "
            "sharp focus, professional studio lighting, photorealistic, high quality, 8k"
        ),
        "negative": (
            "sunglasses, glasses, cartoon, illustration, blurry, watermark, text, "
            "casual clothing, outdoor background, deformed face, extra limbs"
        ),
    },
]

VARIANTS  = 4
WIDTH     = 1024
HEIGHT    = 1024
SEEDS     = [42, 137, 256, 512]


def download_variant(prompt: str, negative: str, seed: int, out_path: Path) -> bool:
    full_prompt = f"{prompt} --no {negative}"
    encoded = urllib.parse.quote(full_prompt)
    url = f"{BASE_URL.format(prompt=encoded)}?width={WIDTH}&height={HEIGHT}&seed={seed}&nologo=true"

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        if "image" not in resp.headers.get("Content-Type", ""):
            print(f"    WARN: unexpected content-type {resp.headers.get('Content-Type')}")
            return False
        out_path.write_bytes(resp.content)
        print(f"    saved  {out_path.name}  ({len(resp.content)//1024} KB)")
        return True
    except Exception as e:
        print(f"    FAIL seed={seed}: {e}")
        return False


def generate_persona(persona: dict) -> None:
    print(f"\nGenerating {persona['label']} ({VARIANTS} variants) ...")
    stem = Path(persona["filename"]).stem
    saved = []

    for i, seed in enumerate(SEEDS[:VARIANTS]):
        var_path = VAR_DIR / f"{stem}_v{i+1}.png"
        ok = download_variant(persona["prompt"], persona["negative"], seed, var_path)
        if ok:
            saved.append(var_path)
        time.sleep(1)   # be polite

    if saved:
        # Copy first variant as canonical file
        canonical = OUT_DIR / persona["filename"]
        canonical.write_bytes(saved[0].read_bytes())
        print(f"  Canonical -> {canonical}")
        print(f"  Review all {len(saved)} variants in avatars/variants/ and replace if needed.")
    else:
        print(f"  All variants failed for {persona['filename']}")


if __name__ == "__main__":
    print("Generating avatar images via Pollinations.ai (free SDXL) ...")
    for persona in PERSONAS:
        generate_persona(persona)
    print("\nDone. Check avatars/variants/ for all options.")
    print("Then run: python tools/image_to_video.py")
