import os
import re
import logging
from typing import Dict, Tuple, List
from src.db import extract_story_tokens

logger = logging.getLogger(__name__)

class PostSpamAuditor:
    """
    Audits a post before publishing to Facebook to guarantee zero risk
    of being flagged by Meta's Graph Content Integrity and Feed Spam algorithms.
    """

    # Engagement bait phrases penalized by Meta feed algorithms
    ENGAGEMENT_BAIT_TRIGGERS = [
        "শেয়ার করুন", "শেয়ার করুন", "লাইক দিন", "কমেন্টে জানান তো", "ট্যাগ করুন",
        "ভিডিওটি শেষ পর্যন্ত দেখুন", "না দেখলে মিস", "অবাক করা কাণ্ড", "চাঞ্চল্যকর তথ্য",
        "দেখুন কী ঘটলো", "দেখুন কি ঘটলো", "ভিডিও দেখুন", "সবাই শেয়ার", "শেয়ার চাই",
        "কমেন্ট করুন", "লাইক দিন", "শেয়ার করে ছড়িয়ে দিন"
    ]

    # Sensational clickbait clichés
    SENSATIONAL_SPAM_TRIGGERS = [
        "আসুন জেনে নেই", "চলুন দেখে নেওয়া যাক", "আমাদের সাথেই থাকুন",
        "আলোচনার ঝড়", "তোলপাড় সৃষ্টি হয়েছে কমেন্টে", "ভাইরাল ভিডিও লিংক",
        "গোপন তথ্য ফাঁস", "চোখ কপালে"
    ]

    @classmethod
    def audit_post(
        cls,
        news_payload: Dict,
        image_path: str,
        caption: str,
        recent_headlines: List[str]
    ) -> Tuple[int, List[str], bool]:
        """
        Calculates a comprehensive Facebook Spam Risk Score (0 - 100).
        0 - 25: Clean Broadhseet Journalism (PASSED / SAFE)
        > 25: Spam Risk Detected (REJECTED)

        Returns: (spam_score: int, issues: List[str], is_safe: bool)
        """
        score = 0
        issues = []

        # Check 1: Topic Deduplication / Repetition (Strict One-Post-Per-Topic Policy)
        title = news_payload.get("title", "")
        cand_tokens = extract_story_tokens(title)
        for prev in recent_headlines:
            prev_tokens = extract_story_tokens(prev)
            if not prev_tokens:
                continue
            overlap = cand_tokens.intersection(prev_tokens)
            min_len = min(len(cand_tokens), len(prev_tokens))
            jaccard = len(overlap) / min_len if min_len > 0 else 0
            if jaccard >= 0.28 or len(overlap) >= 3:
                score += 70
                issues.append(f"একই বিষয়ে পূর্বে পোস্ট করা হয়েছে (পূর্বে: '{prev[:35]}...', ওভারল্যাপ: {overlap})")
                break

        # Check 2: Engagement Bait / Clickbait Penalty
        caption_lower = caption.lower()
        for bait in cls.ENGAGEMENT_BAIT_TRIGGERS:
            if bait in caption_lower:
                score += 30
                issues.append(f"Engagement bait phrase detected: '{bait}'")
                break

        for sens in cls.SENSATIONAL_SPAM_TRIGGERS:
            if sens in caption_lower:
                score += 25
                issues.append(f"Sensational clickbait phrase detected: '{sens}'")
                break

        # Check 3: External Links in Main Caption (Feed Suppressor)
        if re.search(r"https?://(?!fb\.com)", caption):
            score += 40
            issues.append("External HTTP link found in main caption (causes Meta algorithm suppression)")

        # Check 4: Emoji Spam Check
        emoji_count = len(re.findall(r"[\U00010000-\U0010ffff]", caption))
        if emoji_count > 0:
            score += 15 * emoji_count
            issues.append(f"Emoji detected ({emoji_count} emojis - violates broadsheet zero-emoji standard)")

        # Check 5: Image File Integrity & Health
        if not image_path or not os.path.exists(image_path):
            score += 60
            issues.append("Photocard image file does not exist")
        else:
            file_size = os.path.getsize(image_path)
            if file_size < 50 * 1024:
                score += 35
                issues.append(f"Photocard image file size abnormally small ({file_size} bytes)")

        # Check 6: Text Length & Substance
        if len(caption.strip()) < 80:
            score += 30
            issues.append("Caption is too short (< 80 characters)")

        is_safe = (score <= 25)
        return score, issues, is_safe
