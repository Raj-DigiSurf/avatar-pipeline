"""
Avatar Pipeline — Modal Labs Serverless GPU Deployment.

No pod management. No SSH. Just `modal run modal_deploy.py`.

Setup (one-time, ~2 min):
    pip install modal
    modal setup          # opens browser to auth

Usage:
    # Test 5 samples (no upload)
    modal run modal_deploy.py --test

    # Full Part 1 (160 videos, uploads to R2 + updates Supabase)
    modal run modal_deploy.py --part 1

    # All parts (410 videos)
    modal run modal_deploy.py --all

    # Specific JSON file
    modal run modal_deploy.py --exercises content/part2/part2_cuecards.json

Cost: A100 40GB @ ~$0.000544/sec ≈ $1.96/hr — similar to RunPod.
"""

import modal
import os

# ── Modal image: pre-bake all deps so cold start is ~30s ────────────────────

avatar_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("ffmpeg", "git", "wget")
    .pip_install(
        "TTS>=0.22.0",
        "gfpgan>=1.3.8",
        "opencv-python>=4.8.0",
        "ffmpeg-python>=0.2.0",
        "Pillow>=10.0.0",
        "numpy>=1.22.0",
        "boto3>=1.34.0",
        "supabase>=2.4.0",
        "python-dotenv>=1.0.0",
        "tqdm>=4.66.0",
        "requests>=2.31.0",
        "torch>=2.0.0",
        "torchvision",
        "torchaudio",
    )
    # Clone MuseTalk into image
    .run_commands(
        "git clone https://github.com/TMElyralab/MuseTalk /opt/MuseTalk",
        "cd /opt/MuseTalk && pip install -r requirements.txt",
        "wget -q -O /opt/GFPGANv1.4.pth https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth",
    )
)

app = modal.App("avatar-pipeline", image=avatar_image)

# ── Secrets: set these in Modal dashboard (Settings > Secrets) ──────────────
# Create a secret group called "avatar-pipeline" with these keys:
#   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
#   R2_BUCKET_NAME, R2_PUBLIC_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# ── Mount: local project files sent to Modal ────────────────────────────────

local_mount = modal.Mount.from_local_dir(
    ".",
    remote_path="/app",
    condition=lambda path: not any(
        skip in path for skip in [".git", "deps", "output", "__pycache__", ".env"]
    ),
)

# ── GPU function ─────────────────────────────────────────────────────────────

@app.function(
    gpu="A100",
    timeout=7200,          # 2hr max per invocation
    mounts=[local_mount],
    secrets=[modal.Secret.from_name("avatar-pipeline")],
)
def run_batch(exercises_path: str, no_upload: bool = False, limit: int | None = None):
    """Run the avatar pipeline on Modal's A100 GPUs."""
    import subprocess, sys

    os.chdir("/app")

    # Point env at Modal's MuseTalk + GFPGAN
    os.environ["MUSETALK_DIR"] = "/opt/MuseTalk"
    os.environ["GFPGAN_MODEL_PATH"] = "/opt/GFPGANv1.4.pth"
    os.environ["LIPSYNC_BACKEND"] = "musetalk"

    cmd = [
        sys.executable, "generate.py",
        "--exercises", exercises_path,
    ]
    if no_upload:
        cmd.append("--no-upload")
    if limit:
        cmd.extend(["--limit", str(limit)])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Pipeline failed with exit code {result.returncode}")

    # Collect results
    from pathlib import Path
    local_files = list(Path("output/local").glob("*.mp4")) if no_upload else []
    errors_file = Path("output/errors.log")
    errors = errors_file.read_text() if errors_file.exists() else ""

    return {
        "status": "done",
        "local_files": len(local_files),
        "errors": errors or "none",
    }


# ── CLI entrypoint ───────────────────────────────────────────────────────────

@app.local_entrypoint()
def main(
    test: bool = False,
    part: int = 0,
    all: bool = False,
    exercises: str = "",
    dry_run: bool = False,
):
    """
    CLI entrypoint. Examples:
        modal run modal_deploy.py --test
        modal run modal_deploy.py --part 1
        modal run modal_deploy.py --all
        modal run modal_deploy.py --exercises content/part1/part1_topics.json
    """
    jobs = []

    if test:
        jobs.append(("samples/sample_exercises.json", True, 5))
    elif exercises:
        jobs.append((exercises, dry_run, None))
    elif part in (1, 2, 3):
        files = {
            1: "content/part1/part1_topics.json",
            2: "content/part2/part2_cuecards.json",
            3: "content/part3/part3_discussion.json",
        }
        jobs.append((files[part], dry_run, None))
    elif all:
        jobs = [
            ("content/part1/part1_topics.json", dry_run, None),
            ("content/part2/part2_cuecards.json", dry_run, None),
            ("content/part3/part3_discussion.json", dry_run, None),
        ]
    else:
        print("Usage:")
        print("  modal run modal_deploy.py --test          # 5 samples, no upload")
        print("  modal run modal_deploy.py --part 1        # Part 1 (160 videos)")
        print("  modal run modal_deploy.py --part 2        # Part 2 (50 videos)")
        print("  modal run modal_deploy.py --part 3        # Part 3 (200 videos)")
        print("  modal run modal_deploy.py --all           # All 410 videos")
        print("  modal run modal_deploy.py --all --dry-run # All, no upload")
        return

    for path, no_upload, limit in jobs:
        label = path.split("/")[-1]
        print(f"\n{'='*50}")
        print(f"  Launching: {label}")
        print(f"  Upload: {'no' if no_upload else 'yes'}")
        print(f"{'='*50}\n")

        result = run_batch.remote(path, no_upload=no_upload, limit=limit)
        print(f"Result: {result}")

    print("\nAll jobs complete.")
