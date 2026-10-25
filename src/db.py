import re
import difflib
import hashlib
import logging
from typing import Optional, Tuple
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

def extract_story_tokens(text: str) -> set:
    if not text:
        return set()
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s*-\s*[^-]+$", "", clean)
    clean = clean.replace("হাড়", "হাড়").replace("ভাঙল", "ভেঙে").replace("স্ত্রী", "স্ত্রীর").replace("আটক", "গ্রেপ্তার")
    words = re.findall(r"[\u0980-\u09FFa-zA-Z0-9]+", clean.lower())
    stopwords = {
        "ও", "এবং", "বা", "সহ", "১", "২", "৩", "৪", "৫", "ভিডিও", "ভাইরাল", 
        "এক", "এই", "সেই", "নিয়ে", "পর", "হলো", "হলে", "থেকে", "করে", 
        "হয়েছে", "বার্তা", "সংবাদ", "খবর", "উত্তরবঙ্গ", "সারা", "দেশ"
    }
    return {w for w in words if w not in stopwords and len(w) > 1}

def is_duplicate_story(candidate_title: str, candidate_summary: str, recent_headlines: list) -> Tuple[bool, str]:
    """
    Checks whether a candidate news item is about the exact same story as any recently published headline.
    Enforces the rule: Same topic cannot be repeated unless there is an authentic subsequent stage/development.
    Returns (is_duplicate: bool, reason: str).
    """
    cand_tokens = extract_story_tokens(candidate_title)
    if not cand_tokens:
        return False, ""

    full_candidate_text = f"{candidate_title} {candidate_summary}"
    
    NEXT_STAGE_KEYWORDS = [
        "তদন্ত কমিটি", "তদন্ত", "গ্রেপ্তার", "আটক", "মামলা",
        "প্রত্যাহার", "ওএসডি", "অ্যাকশন", "আইনি পদক্ষেপ", "নতুন মোড়",
        "সর্বশেষ আপডেট", "রিমান্ড", "উদ্ধার", "স্বীকারোক্তি", "বহিষ্কার"
    ]

    for prev in recent_headlines:
        prev_tokens = extract_story_tokens(prev)
        if not prev_tokens:
            continue

        overlap = cand_tokens.intersection(prev_tokens)
        min_len = min(len(cand_tokens), len(prev_tokens))
        jaccard = len(overlap) / min_len if min_len > 0 else 0
        seq_ratio = difflib.SequenceMatcher(None, candidate_title, prev).ratio()

        if jaccard >= 0.40 or seq_ratio >= 0.50 or len(overlap) >= 3:
            matching_stages = [kw for kw in NEXT_STAGE_KEYWORDS if kw in full_candidate_text]
            has_new_stage = bool(matching_stages)
            prev_has_same_stage = any(kw in prev for kw in matching_stages)
            
            if has_new_stage and not prev_has_same_stage:
                return False, f"নতুন স্টেজ বা অগ্রগতি ({matching_stages})"
            else:
                return True, f"একই ঘটনার পুনরাবৃত্তি (পূর্বে প্রকাশিত: '{prev[:35]}...', ওভারল্যাপ: {overlap})"

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
            err_dict = getattr(e, 'args', [{}])[0] if hasattr(e, 'args') and len(e.args) > 0 else {}
            if isinstance(err_dict, dict) and err_dict.get("code") == "42501":
                logger.error("🚨 SUPABASE RLS ERROR (42501): Table 'posts' has Row Level Security (RLS) enabled without an INSERT policy! Please run 'ALTER TABLE posts DISABLE ROW LEVEL SECURITY;' in Supabase SQL editor.")
            else:
                logger.error(f"Failed to save post in Supabase: {e}")
            return False
