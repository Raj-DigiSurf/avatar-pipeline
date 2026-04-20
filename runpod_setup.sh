#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# RunPod one-shot setup + test script
# Run this once after spinning up an A100 pod.
#
# Usage:
#   chmod +x runpod_setup.sh
#   ./runpod_setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo ""
echo "=== Avatar Pipeline — RunPod Setup ==="
echo ""

# ── 1. Python deps ────────────────────────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip3 install -q -r requirements.txt

# ── 2. Clone MuseTalk ─────────────────────────────────────────────────────────
echo "[2/5] Cloning MuseTalk..."
mkdir -p deps
if [ ! -d "deps/MuseTalk" ]; then
    git clone https://github.com/TMElyralab/MuseTalk deps/MuseTalk
    cd deps/MuseTalk
    pip3 install -q -r requirements.txt
    cd ../..
    echo "    MuseTalk installed."
else
    echo "    MuseTalk already present, skipping."
fi

# ── 3. Download GFPGAN model ──────────────────────────────────────────────────
echo "[3/5] Downloading GFPGAN model..."
mkdir -p deps
if [ ! -f "deps/GFPGANv1.4.pth" ]; then
    wget -q -O deps/GFPGANv1.4.pth \
        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth"
    echo "    GFPGANv1.4.pth downloaded."
else
    echo "    GFPGAN model already present, skipping."
fi

# ── 4. Check .env ─────────────────────────────────────────────────────────────
echo "[4/5] Checking .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "    *** .env created from .env.example ***"
    echo "    Fill in your R2 and Supabase credentials before running the pipeline:"
    echo "    nano .env"
    echo ""
else
    echo "    .env found."
fi

# ── 5. Run 5-sample test ──────────────────────────────────────────────────────
echo "[5/5] Running 5-sample test..."
echo ""
echo "Choose test mode:"
echo "  a) Full test — real lipsync + R2 upload + Supabase (needs .env filled)"
echo "  b) Local test — real lipsync, NO upload (outputs saved to output/local/)"
echo "  c) Skip lipsync — TTS + static video + upload (quick connectivity test)"
echo ""
read -rp "Enter a, b, or c: " mode

case "$mode" in
    a)
        python3 generate.py --exercises samples/sample_exercises.json
        ;;
    b)
        python3 generate.py --exercises samples/sample_exercises.json --no-upload
        echo "Videos saved to output/local/"
        ;;
    c)
        python3 generate.py --exercises samples/sample_exercises.json --skip-lipsync
        ;;
    *)
        echo "Invalid choice. Run manually:"
        echo "  python generate.py --exercises samples/sample_exercises.json --no-upload"
        ;;
esac

echo ""
echo "=== Setup complete ==="
