"""
Cloudflare R2 upload — boto3 with S3-compatible endpoint.

Required .env vars:
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
  R2_BUCKET_NAME, R2_PUBLIC_URL
"""

import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


class R2Uploader:
    def __init__(self):
        account_id = os.getenv("R2_ACCOUNT_ID")
        if not account_id:
            raise EnvironmentError("R2_ACCOUNT_ID not set in environment.")

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
        )
        self.bucket = os.getenv("R2_BUCKET_NAME")
        self.public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

    def upload(self, local_path: str | Path, key: str) -> str:
        """
        Upload `local_path` to R2 at `key`.
        Returns the public URL.

        Key convention:
          ielts/academic/speaking/part{N}/{exercise_id}.mp4
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"File to upload not found: {local_path}")

        try:
            self.client.upload_file(
                str(local_path),
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": "video/mp4",
                    "CacheControl": "public, max-age=31536000",
                },
            )
        except ClientError as e:
            raise RuntimeError(f"R2 upload failed for {key}: {e}") from e

        url = f"{self.public_url}/{key}"
        log.info("Uploaded %s → %s", local_path.name, url)
        return url

    @staticmethod
    def make_key(exercise_id: str, part: int) -> str:
        """Build the canonical R2 object key for a given exercise."""
        return f"ielts/academic/speaking/part{part}/{exercise_id}.mp4"
