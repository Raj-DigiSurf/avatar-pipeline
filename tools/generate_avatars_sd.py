"""
Generate photorealistic examiner avatars using Stable Diffusion XL.

Run this on RunPod A100 (or any GPU with 12GB+ VRAM).

Setup on RunPod:
  pip install diffusers transformers accelerate safetensors Pillow

Run:
  python tools/generate_avatars_sd.py

Output: avatars/older_man.png, avatars/woman.png, avatars/younger_man.png
        Each image is 1024x1024, photorealistic, professional headshot.

After generation, run:
  python tools/image_to_video.py   (convert PNG -> looping MP4 for MuseTalk)
"""

import torch
from pathlib import Path
from diffusers import StableDiffusionXLPipeline

OUT_DIR = Path("avatars")
OUT_DIR.mkdir(exist_ok=True)

# ── Model ─────────────────────────────────────────────────────────────────────
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"

# ── Persona definitions ────────────────────────────────────────────────────────
# Matches the DigiSurf PDF examiner personas exactly.
PERSONAS = [
    {
        "filename": "older_man.png",
        "prompt": (
            "professional headshot portrait photograph of a 58-year-old male IELTS examiner, "
            "white silver hair neatly combed, wearing a navy blue suit and blue tie, "
            "light blue shirt, neutral friendly expression, looking directly at camera, "
            "plain light grey studio background, sharp focus, studio lighting, "
            "photorealistic, 8k, high quality, no glasses"
        ),
        "negative_prompt": (
            "sunglasses, glasses, eyewear, cartoon, illustration, drawing, painting, "
            "blurry, low quality, deformed face, extra limbs, watermark, text, logo, "
            "casual clothing, hoodie, t-shirt, outdoor background, dark background"
        ),
    },
    {
        "filename": "woman.png",
        "prompt": (
            "professional headshot portrait photograph of a 38-year-old female IELTS examiner, "
            "blonde hair shoulder length, wearing a dark charcoal blazer jacket, "
            "white blouse, neutral professional expression, looking directly at camera, "
            "plain light grey studio background, sharp focus, studio lighting, "
            "photorealistic, 8k, high quality, no glasses"
        ),
        "negative_prompt": (
            "sunglasses, glasses, eyewear, cartoon, illustration, drawing, painting, "
            "blurry, low quality, deformed face, extra limbs, watermark, text, logo, "
            "casual clothing, hoodie, outdoor background, dark background, male"
        ),
    },
    {
        "filename": "younger_man.png",
        "prompt": (
            "professional headshot portrait photograph of a 32-year-old male IELTS examiner, "
            "short dark brown hair, clean shaven, wearing a light grey suit and dark tie, "
            "white shirt, neutral professional expression, looking directly at camera, "
            "plain light grey studio background, sharp focus, studio lighting, "
            "photorealistic, 8k, high quality, no glasses"
        ),
        "negative_prompt": (
            "sunglasses, glasses, eyewear, cartoon, illustration, drawing, painting, "
            "blurry, low quality, deformed face, extra limbs, watermark, text, logo, "
            "casual clothing, hoodie, outdoor background, dark background, female, old"
        ),
    },
]

# ── Generation settings ────────────────────────────────────────────────────────
NUM_STEPS          = 40
GUIDANCE_SCALE     = 7.5
SEED               = 42          # change seed to get different faces
NUM_IMAGES_PER_RUN = 4           # generates 4 variants, saves the best (first) one


def load_pipeline() -> StableDiffusionXLPipeline:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype  = torch.float16 if device == "cuda" else torch.float32
    print(f"Loading SDXL on {device} (dtype={dtype}) ...")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        use_safetensors=True,
        variant="fp16" if device == "cuda" else None,
    ).to(device)
    pipe.enable_attention_slicing()
    if device == "cuda":
        pipe.enable_xformers_memory_efficient_attention()
    return pipe


def generate_persona(pipe, persona: dict) -> None:
    out_path = OUT_DIR / persona["filename"]
    print(f"\nGenerating {persona['filename']} ...")

    generator = torch.Generator().manual_seed(SEED)
    images = pipe(
        prompt          = persona["prompt"],
        negative_prompt = persona["negative_prompt"],
        num_images_per_prompt = NUM_IMAGES_PER_RUN,
        num_inference_steps   = NUM_STEPS,
        guidance_scale        = GUIDANCE_SCALE,
        generator             = generator,
        height = 1024,
        width  = 1024,
    ).images

    # Save all variants for review, keep the first as the canonical file
    variants_dir = OUT_DIR / "variants"
    variants_dir.mkdir(exist_ok=True)
    stem = out_path.stem

    for i, img in enumerate(images):
        variant_path = variants_dir / f"{stem}_v{i + 1}.png"
        img.save(str(variant_path))
        print(f"  Saved variant: {variant_path}")

    # Save variant 1 as the canonical avatar
    images[0].save(str(out_path))
    print(f"  Canonical: {out_path}")
    print(f"  Review all variants in avatars/variants/ and replace {out_path} with the best one.")


if __name__ == "__main__":
    pipe = load_pipeline()
    for persona in PERSONAS:
        generate_persona(pipe, persona)

    print("\n\nAll personas generated.")
    print("Review avatars/variants/ and copy your preferred variant over the canonical file.")
    print("Then run:  python tools/image_to_video.py")
