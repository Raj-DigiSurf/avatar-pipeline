#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Run full IELTS Academic Speaking batch (all 410 videos)
# Part 1: 160 videos | Part 2: 50 videos | Part 3: 200 videos
#
# Usage:
#   bash run_all.sh              # all parts
#   bash run_all.sh 1            # Part 1 only
#   bash run_all.sh 2            # Part 2 only
#   bash run_all.sh 3            # Part 3 only
#   bash run_all.sh --dry-run    # all parts, no upload
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

EXTRA_FLAGS=""
PARTS="1 2 3"

for arg in "$@"; do
    case "$arg" in
        1|2|3) PARTS="$arg" ;;
        --dry-run) EXTRA_FLAGS="--no-upload" ;;
    esac
done

echo ""
echo "=== Avatar Pipeline — Full Batch ==="
echo "Parts: $PARTS"
echo "Extra flags: ${EXTRA_FLAGS:-none}"
echo ""

for part in $PARTS; do
    case "$part" in
        1) file="content/part1/part1_topics.json";     label="Part 1 (160 questions)" ;;
        2) file="content/part2/part2_cuecards.json";   label="Part 2 (50 cue cards)" ;;
        3) file="content/part3/part3_discussion.json"; label="Part 3 (200 questions)" ;;
    esac

    echo ""
    echo "────────────────────────────────────────"
    echo "  Starting $label"
    echo "────────────────────────────────────────"
    python3 generate.py --exercises "$file" $EXTRA_FLAGS
done

echo ""
echo "=== All batches complete ==="
echo "Check output/errors.log for any failures."
echo ""
