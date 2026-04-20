"""
Supabase — update exercises table with generated video URL.

Required .env vars:  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Table expected:
  exercises (
    id                  text PRIMARY KEY,
    examiner_video_url  text
  )

Run this migration once if the column doesn't exist yet:
  ALTER TABLE exercises ADD COLUMN IF NOT EXISTS examiner_video_url TEXT DEFAULT NULL;
"""

import logging
import os

from supabase import create_client, Client

log = logging.getLogger(__name__)


class ExerciseDB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        self.client: Client = create_client(url, key)

    def update_video_url(self, exercise_id: str, url: str) -> None:
        """Set examiner_video_url for the given exercise row."""
        response = (
            self.client.table("exercises")
            .update({"examiner_video_url": url})
            .eq("id", exercise_id)
            .execute()
        )
        if not response.data:
            log.warning("No row updated for exercise_id=%s — does it exist in exercises table?", exercise_id)
        else:
            log.debug("DB updated: %s → %s", exercise_id, url)

    def get_pending(self, part: int | None = None) -> list[dict]:
        """
        Fetch exercises that don't yet have a video URL.
        Optionally filter by part number (1, 2, or 3).
        """
        query = (
            self.client.table("exercises")
            .select("id, part, avatar, text")
            .is_("examiner_video_url", "null")
        )
        if part is not None:
            query = query.eq("part", part)
        return query.execute().data or []
