#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Avatar Pipeline — RunPod One-Shot Deploy
#
# Run this ONCE after spinning up a RunPod A100 GPU pod.
# It clones the repo, installs everything, and runs a 5-sample test.
#
# Prerequisites:
#   - RunPod pod with PyTorch template (comes with CUDA + torch pre-installed)
#   - Git access to repo (HTTPS or SSH)
#
# Usage:
#   # Option A: curl from GitHub (paste into RunPod terminal)
#   curl -sL https://raw.githubusercontent.com/Raj-DigiSurf/avatar-pipeline/master/deploy_runpod.sh | bash
#
#   # Option B: if repo is already cloned
#   cd Avatar-Pipeline && bash deploy_runpod.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Avatar Pipeline — RunPod Deploy            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

WORKDIR="/workspace/Avatar-Pipeline"

# ── 1. Clone repo if not already present ─────────────────────────────────────
if [ ! -d "$WORKDIR" ]; then
    echo "[1/8] Cloning repository..."
    cd /workspace
    git clone https://github.com/Raj-DigiSurf/avatar-pipeline.git Avatar-Pipeline
    cd "$WORKDIR"
    echo "    ✓ Cloned to $WORKDIR"
else
    cd "$WORKDIR"
    echo "[1/8] Repo already at $WORKDIR — pulling latest..."
    git pull --ff-only || echo "    (pull skipped — local changes present)"
fi

# ── 2. Check .env ────────────────────────────────────────────────────────────
echo "[2/8] Checking .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ╔═══════════════════════════════════════════════════════╗"
    echo "  ║  .env created from .env.example                      ║"
    echo "  ║  Fill in your R2 + Supabase credentials:             ║"
    echo "  ║    nano .env                                         ║"
    echo "  ║  Then re-run: bash deploy_runpod.sh                  ║"
    echo "  ╚═══════════════════════════════════════════════════════╝"
    echo ""
    exit 1
else
    # Verify critical vars are not placeholder
    source .env 2>/dev/null || true
    if [[ "$R2_ACCOUNT_ID" == "your_"* ]] || [[ -z "$R2_ACCOUNT_ID" ]]; then
        echo "  ⚠  .env has placeholder values — fill in real credentials first."
        echo "     nano .env"
        exit 1
    fi
    echo "    ✓ .env found with credentials"
fi

# ── 3. Install Python deps ──────────────────────────────────────────────────
echo "[3/8] Installing Python dependencies..."
pip3 install -q -r requirements.txt 2>&1 | tail -5
echo "    ✓ Python deps installed"

# ── 4. Install PyTorch with CUDA (skip if already present) ──────────────────
echo "[4/8] Checking PyTorch + CUDA..."
python3 -c "import torch; assert torch.cuda.is_available(), 'No CUDA'; print(f'    ✓ PyTorch {torch.__version__} + CUDA {torch.version.cuda} ({torch.cuda.get_device_name(0)})')" 2>/dev/null \
    || {
        echo "    Installing PyTorch with CUDA 11.8..."
        pip3 install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
        python3 -c "import torch; print(f'    ✓ PyTorch {torch.__version__} + CUDA {torch.version.cuda}')"
    }

# ── 5. Clone MuseTalk ───────────────────────────────────────────────────────
echo "[5/8] Setting up MuseTalk..."
mkdir -p deps
if [ ! -d "deps/MuseTalk" ]; then
    git clone https://github.com/TMElyralab/MuseTalk deps/MuseTalk
    cd deps/MuseTalk
    pip3 install -q -r requirements.txt 2>&1 | tail -3
    cd "$WORKDIR"
    echo "    ✓ MuseTalk cloned + deps installed"
else
    echo "    ✓ MuseTalk already present"
fi

# ── 6. Download GFPGAN model ────────────────────────────────────────────────
echo "[6/8] Downloading GFPGAN model..."
if [ ! -f "deps/GFPGANv1.4.pth" ]; then
    wget -q -O deps/GFPGANv1.4.pth \
        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth"
    echo "    ✓ GFPGANv1.4.pth downloaded"
else
    echo "    ✓ GFPGAN model already present"
fi

# ── 7. Generate reference voice WAVs for XTTS-v2 ────────────────────────────
echo "[7/8] Generating reference voice WAVs..."
if [ ! -f "avatars/voices/default.wav" ]; then
    python3 tools/generate_voices.py
    echo "    ✓ Voice references generated"
else
    echo "    ✓ Voice references already present"
fi

# ── 8. Run 5-sample test ────────────────────────────────────────────────────
echo "[8/8] Running 5-sample test (real lipsync, no upload)..."
echo ""
python3 generate.py --exercises samples/sample_exercises.json --no-upload
echo ""

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✓ Deploy complete!                                         ║"
echo "║                                                              ║"
echo "║  Test videos saved to: output/local/                         ║"
echo "║                                                              ║"
echo "║  Next commands:                                              ║"
echo "║    # Review test output                                      ║"
echo "║    ls -lh output/local/                                      ║"
echo "║                                                              ║"
echo "║    # Run with R2 upload + Supabase                           ║"
echo "║    python3 generate.py \                                     ║"
echo "║      --exercises samples/sample_exercises.json               ║"
echo "║                                                              ║"
echo "║    # Full Part 1 batch (160 videos)                          ║"
echo "║    python3 generate.py \                                     ║"
echo "║      --exercises content/part1/part1_topics.json             ║"
echo "║                                                              ║"
echo "║    # Full IELTS batch (all 410 videos)                       ║"
echo "║    bash run_all.sh                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
