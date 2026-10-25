import re
import os
import difflib
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

def normalize_bengali_word(w: str) -> str:
    """Strips Bengali inflectional suffixes (genitive, locative, plural) for deep semantic matching."""
    w = w.replace("হাড়", "হাড়").replace("ভাঙল", "ভেঙে").replace("আটক", "গ্রেপ্তার")
    suffixes = ["গুলোর", "গুলো", "দের", "ের", "কে", "তে", "র", "য়", "ে"]
    for suf in suffixes:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w

def extract_story_tokens(text: str) -> set:
    if not text:
        return set()
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s*-\s*[^-]+$", "", clean)
    clean = clean.replace("হাড়", "হাড়").replace("ভাঙল", "ভেঙে")
    words = re.findall(r"[\u0980-\u09FFa-zA-Z0-9]+", clean.lower())
    stopwords = {
        "ও", "এবং", "বা", "সহ", "১", "২", "৩", "৪", "৫", "ভিডিও", "ভাইরাল", 
        "এক", "এই", "সেই", "নিয়ে", "পর", "হলো", "হলে", "থেকে", "করে", 
        "হয়েছে", "বার্তা", "সংবাদ", "খবর", "উত্তরবঙ্গ", "সারা", "দেশ"
    }
    raw_tokens = {w for w in words if w not in stopwords and len(w) > 1}
    normalized = {normalize_bengali_word(w) for w in raw_tokens}
    return raw_tokens.union(normalized)

def is_duplicate_story(candidate_title: str, candidate_summary: str, recent_headlines: list) -> Tuple[bool, str]:
    """
    Checks whether a candidate news item is about the exact same story as any recently published headline.
    STRICT ANTI-SPAM POLICY: One post per topic. No next stage or subsequent updates to prevent Facebook spam classification.
    Returns (is_duplicate: bool, reason: str).
    """
    cand_tokens = extract_story_tokens(candidate_title)
    if not cand_tokens:
        return False, ""

    for prev in recent_headlines:
        prev_tokens = extract_story_tokens(prev)
        if not prev_tokens:
            continue

        overlap = cand_tokens.intersection(prev_tokens)
        min_len = min(len(cand_tokens), len(prev_tokens))
        jaccard = len(overlap) / min_len if min_len > 0 else 0
        seq_ratio = difflib.SequenceMatcher(None, candidate_title, prev).ratio()

        if jaccard >= 0.28 or seq_ratio >= 0.45 or len(overlap) >= 3:
            return True, f"ফেসবুক স্প্যাম ফিল্টার সুরক্ষায় একই বিষয়ের খবর একবারই পোস্ট হবে। পূর্বে প্রকাশিত: '{prev[:35]}...' (ওভারল্যাপ: {overlap})"

    return False, ""

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

    def get_recent_headlines(self, limit: int = 50) -> list:
        """Fetches the recent published headlines to detect evolving storylines and avoid duplicate stages."""
        if not self.client:
            return []
        try:
            res = self.client.table("posts").select("headline").order("created_at", desc=True).limit(limit).execute()
            if res.data:
                return [r.get("headline", "") for r in res.data if r.get("headline")]
            return []
        except Exception as e:
            logger.debug(f"Could not fetch recent headlines from Supabase: {e}")
            return []

    def get_all_posts(self, limit: int = 100) -> list:
        """Fetches detailed published post records for the Admin Dashboard."""
        if not self.client:
            return []
        try:
            res = self.client.table("posts").select("*").order("created_at", desc=True).limit(limit).execute()
            return res.data if res.data else []
        except Exception as e:
            logger.error(f"Error fetching all posts from Supabase: {e}")
            return []

    def delete_post_by_hash(self, url_hash: str) -> Optional[dict]:
        """Deletes a post record from Supabase table 'posts' by url_hash and returns deleted row."""
        if not self.client:
            return None
        try:
            # First fetch the row to get fb_post_id
            row_res = self.client.table("posts").select("*").eq("url_hash", url_hash).execute()
            row_data = row_res.data[0] if row_res.data else None

            # Delete the record
            self.client.table("posts").delete().eq("url_hash", url_hash).execute()
            logger.info(f"Deleted post record from Supabase: {url_hash[:10]}...")
            return row_data
        except Exception as e:
            logger.error(f"Failed to delete post from Supabase: {e}")
            return None

    def get_last_template(self) -> Optional[str]:
        """
        Retrieves the template used in the most recently published post.
        Checks Supabase first, with a fallback to local cache.
        """
        if self.client:
            try:
                res = self.client.table("posts").select("fb_post_id").order("created_at", desc=True).limit(5).execute()
                if res.data:
                    for row in res.data:
                        fb_pid = row.get("fb_post_id", "")
                        if fb_pid and "|tmpl:" in fb_pid:
                            tmpl = fb_pid.split("|tmpl:", 1)[1].strip()
                            if tmpl:
                                return tmpl
            except Exception as e:
                logger.debug(f"Could not fetch last template from Supabase: {e}")

        # Local fallback cache
        if os.path.exists(".last_template"):
            try:
                with open(".last_template", "r", encoding="utf-8") as f:
                    cached_tmpl = f.read().strip()
                    if cached_tmpl:
                        return cached_tmpl
            except Exception:
                pass
        return None

    def get_minutes_since_last_post(self) -> Optional[float]:
        """
        Returns how many minutes have elapsed since the last post was created.
        Used to enforce safe pacing intervals (minimum 25-30 min) to avoid Facebook spam detection.
        """
        if self.client:
            try:
                res = self.client.table("posts").select("created_at").order("created_at", desc=True).limit(1).execute()
                if res.data and res.data[0].get("created_at"):
                    created_at_str = res.data[0]["created_at"].replace("Z", "+00:00")
                    last_dt = datetime.fromisoformat(created_at_str)
                    now_dt = datetime.now(timezone.utc)
                    elapsed_minutes = (now_dt - last_dt).total_seconds() / 60.0
                    return elapsed_minutes
            except Exception as e:
                logger.debug(f"Could not compute minutes since last post from Supabase: {e}")

        # Local fallback
        if os.path.exists(".last_posted_time"):
            try:
                with open(".last_posted_time", "r", encoding="utf-8") as f:
                    ts = float(f.read().strip())
                    elapsed = (datetime.now(timezone.utc).timestamp() - ts) / 60.0
                    return elapsed
            except Exception:
                pass
        return None

    def save_post(self, news_url: str, headline: str, fb_post_id: str = "dry_run", template: Optional[str] = None) -> bool:
        """Records a successful post in Supabase with template metadata and local fallback cache."""
        stored_post_id = f"{fb_post_id}|tmpl:{template}" if template else fb_post_id

        # Update local caches
        try:
            if template:
                with open(".last_template", "w", encoding="utf-8") as f:
                    f.write(template)
            with open(".last_posted_time", "w", encoding="utf-8") as f:
                f.write(str(datetime.now(timezone.utc).timestamp()))
        except Exception:
            pass

        if not self.client:
            return False

        url_hash = self.get_hash(news_url)
        try:
            self.client.table("posts").insert({
                "url_hash": url_hash,
                "news_url": news_url,
                "headline": headline,
                "fb_post_id": stored_post_id
            }).execute()
            logger.info(f"Saved post signature to Supabase: {url_hash[:10]}... (Template: {template or 'default'})")
            return True
        except Exception as e:
            err_dict = getattr(e, 'args', [{}])[0] if hasattr(e, 'args') and len(e.args) > 0 else {}
            if isinstance(err_dict, dict) and err_dict.get("code") == "42501":
                logger.error("🚨 SUPABASE RLS ERROR (42501): Table 'posts' has Row Level Security (RLS) enabled without an INSERT policy! Please run 'ALTER TABLE posts DISABLE ROW LEVEL SECURITY;' in Supabase SQL editor.")
            else:
                logger.error(f"Failed to save post in Supabase: {e}")
            return False
