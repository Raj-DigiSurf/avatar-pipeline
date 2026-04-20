# Avatar-Pipeline — Agent Instructions

## What This Project Is
Standalone Python batch pipeline to generate AI avatar examiner videos for DigiSurf products.
Consumes exercise JSON → outputs lip-synced MP4s stored on Cloudflare R2.

## Always Read First
Before any session: read `memory/project_avatar_pipeline.md` for current status + next steps.

## Stack
- Python 3.10+
- MuseTalk (lip-sync, primary)
- SadTalker (lip-sync, fallback)
- XTTS-v2 / Coqui TTS (voice synthesis)
- GFPGAN (face enhancement)
- ffmpeg (video encoding)
- Cloudflare R2 (storage, boto3 with custom endpoint)
- Supabase (update exercise rows with final MP4 URL)
- RunPod A100 (GPU runtime) or Modal Labs (serverless GPU)

## Env vars (in .env)
- `R2_ACCOUNT_ID` — Cloudflare account ID
- `R2_ACCESS_KEY_ID` — R2 access key
- `R2_SECRET_ACCESS_KEY` — R2 secret
- `R2_BUCKET_NAME` — bucket name
- `R2_PUBLIC_URL` — public CDN base URL
- `SUPABASE_URL` — same project as Spoken English
- `SUPABASE_SERVICE_ROLE_KEY` — service role (can update exercises table)

## Key Conventions
- Avatar photos live in `avatars/` (PNG, 512x512+, frontal, neutral)
- Temp audio/video during processing goes in `output/` (gitignored)
- Final MP4s go to R2, never committed to git
- Exercise data pulled from Supabase `exercises` table (or local JSON files in Spoken-English repo)
- Always update `exercises.examiner_video_url` after successful upload
- Log failures to `output/errors.log`, never crash entire batch on one failure

## Obsidian Vault
- Vault: `C:\Users\Cipher\Downloads\notes\`
- Project note: `notes/projects/Avatar-Pipeline.md`
- Reference: `notes/reference/AI-Avatar-Pipeline.md`

## Related Projects
- `C:\Users\Cipher\Downloads\Spoken-English\` — first consumer of generated videos
- Future: IELTS, PTE, Life Skills, OET, CELPIP modules
