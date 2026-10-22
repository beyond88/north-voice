import hashlib
import logging
from typing import Optional
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client: Optional[Client] = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Connected to Supabase successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Supabase: {e}")
        else:
            logger.warning("Supabase credentials not configured. Running in stateless mode.")

    @staticmethod
    def get_hash(text: str) -> str:
        """Generates a SHA-256 hash of a URL or headline for quick duplicate checks."""
        # Normalize by stripping trailing slashes and lowercasing
        clean_text = text.strip().rstrip("/").lower()
        return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

    def is_already_posted(self, url_or_title: str) -> bool:
        """Returns True if the news item hash exists in the 'posts' table."""
        if not self.client:
            return False

        url_hash = self.get_hash(url_or_title)
        try:
            res = self.client.table("posts").select("id").eq("url_hash", url_hash).execute()
            if res.data and len(res.data) > 0:
                logger.info(f"Duplicate found for hash: {url_hash[:10]}...")
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking duplicate in Supabase: {e}")
            return False

    def save_post(self, news_url: str, headline: str, fb_post_id: str = "dry_run") -> bool:
        """Records a successful post in Supabase."""
        if not self.client:
            return False

        url_hash = self.get_hash(news_url)
        try:
            self.client.table("posts").insert({
                "url_hash": url_hash,
                "news_url": news_url,
                "headline": headline,
                "fb_post_id": fb_post_id
            }).execute()
            logger.info(f"Saved post signature to Supabase: {url_hash[:10]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to save post in Supabase: {e}")
            return False
