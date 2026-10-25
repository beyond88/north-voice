import re
import datetime
import logging
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import requests
import feedparser
from bs4 import BeautifulSoup
from src.config import RSS_FEEDS, NORTH_BENGAL_DISTRICTS, NORTH_BENGAL_UPAZILAS

logger = logging.getLogger(__name__)

def is_valid_image_url(url: Optional[str]) -> bool:
    """Verifies that an image URL is a real photograph and not a search engine icon, site logo, or placeholder."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False
    u = url.lower()
    invalid_patterns = [
        "googleusercontent.com", "news.google.com", "gstatic.com", "google.com",
        "default", "placeholder", "blank", "facebook-share", "favicon", "app-icon",
        "site-logo", "brand-logo", "fallback", "avatar", "profile", "handcuff",
        "vector", "clipart", "illustration", "svg"
    ]
    return not any(pat in u for pat in invalid_patterns)

class NewsHunter:
    def __init__(self):
        self.districts = NORTH_BENGAL_DISTRICTS
        self.upazilas_map = NORTH_BENGAL_UPAZILAS

        # Reverse lookup map: upazila_name -> district_name
        self.upazila_to_district = {}
        for dist, upazila_list in self.upazilas_map.items():
            for u in upazila_list:
                self.upazila_to_district[u] = dist

    def clean_html(self, html_text: str) -> str:
        """Strips HTML tags and returns clean text."""
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, "html.parser")
        return soup.get_text(separator=" ").strip()

    def extract_image(self, entry) -> Optional[str]:
        """Tries to extract the highest quality image url from the RSS entry."""
        # 1. Media content
        if "media_content" in entry and entry["media_content"]:
            for media in entry["media_content"]:
                if "url" in media and is_valid_image_url(media["url"]):
                    return media["url"]

        # 2. Enclosures
        if "enclosures" in entry and entry["enclosures"]:
            for enc in entry["enclosures"]:
                href = enc.get("href", "")
                if href and is_valid_image_url(href) and ("image" in enc.get("type", "") or href.endswith((".jpg", ".png", ".jpeg", ".webp"))):
                    return href

        # 3. Media thumbnail
        if "media_thumbnail" in entry and entry["media_thumbnail"]:
            thumb_url = entry["media_thumbnail"][0].get("url")
            if is_valid_image_url(thumb_url):
                return thumb_url

        # 4. Search within HTML summary / description
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary:
            soup = BeautifulSoup(summary, "html.parser")
            img = soup.find("img")
            if img and img.get("src") and is_valid_image_url(img["src"]):
                return img["src"]

        return None

    def fetch_og_image(self, url: str) -> Optional[str]:
        """Fetches high-res og:image or twitter:image from article webpage as fallback."""
        if not url:
            return None
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(url, headers=headers, timeout=6, allow_redirects=True)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for prop in ["og:image", "og:image:url", "og:image:secure_url", "twitter:image"]:
                    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                    if tag and tag.get("content"):
                        img = tag["content"].strip()
                        if is_valid_image_url(img):
                            return img
        except Exception as e:
            logger.debug(f"Could not fetch og:image from {url}: {e}")
        return None

    def resolve_article_meta(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Resolves the true destination URL and real authentic news image.
        For Google News redirect links, uses Playwright to follow client-side redirects to destination publisher.
        Returns (resolved_url, og_image_url).
        """
        if not url:
            return url, None
            
        if "news.google.com" in url:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url, timeout=12000)
                    page.wait_for_timeout(1500)
                    resolved_url = page.url
                    og_img = None
                    og_tag = page.locator("meta[property=\"og:image\"], meta[property=\"og:image:url\"], meta[name=\"twitter:image\"]").first
                    if og_tag.count() > 0:
                        raw_img = og_tag.get_attribute("content")
                        if is_valid_image_url(raw_img):
                            og_img = raw_img
                    browser.close()
                    return resolved_url, og_img
            except Exception as e:
                logger.debug(f"Could not resolve Google News url via Playwright: {e}")
                
        # Default requests-based resolution
        og_img = self.fetch_og_image(url)
        return url, og_img

    AMBIGUOUS_UPAZILAS = {
        "বিরল": ["দিনাজপুর", "উপজেলা", "থানা"],
        "বেড়া": ["পাবনা", "উপজেলা", "থানা"],
        "কিশোরগঞ্জ": ["নীলফামারী", "উপজেলা", "থানা"],
        "শেরপুর": ["বগুড়া", "বগুড়ার"],
        "ফরিদপুর": ["পাবনা", "পাবনার"]
    }

    INTERNATIONAL_COUNTRIES = [
        "চীন", "চীনে", "চীনের", "বেইজিং",
        "ভারত", "ভারতে", "ভারতের", "নয়াদিল্লি", "দিল্লি", "কলকাতা",
        "যুক্তরাষ্ট্র", "যুক্তরাষ্ট্রের", "আমেরিকা", "আমেরিকায়", "মার্কিন", "ওয়াশিংটন",
        "যুক্তরাজ্য", "যুক্তরাজ্যের", "ব্রিটেন", "ব্রিটেনের", "লন্ডন",
        "রাশিয়া", "রাশিয়ার", "মস্কো",
        "ইউক্রেন", "ইউক্রেনের", "কিয়েভ",
        "পাকিস্তান", "পাকিস্তানে", "পাকিস্তানের", "ইসলামাবাদ",
        "ফিলিস্তিন", "ফিলিস্তিনের", "গাজা", "গাজায়", "রাফাহ",
        "ইসরায়েল", "ইসরায়েলে", "ইসরায়েলের", "তেল আবিব",
        "ইরান", "ইরানে", "ইরানের", "তেহরান",
        "লেবানন", "লেবাননে", "লেবাননের", "বৈরুত",
        "সৌদি", "সৌদি আরব", "সৌদি আরবে", "রিয়াদ", "মক্কা", "মদিনা",
        "দুবাই", "সংযুক্ত আরব আমিরাত", "ইউএই", "কাতার", "দোহা",
        "তুরস্ক", "তুরস্কে", "ইস্তাম্বুল", "আঙ্কারা",
        "মালয়েশিয়া", "মালয়েশিয়ায়", "কুয়ালালামপুর",
        "সিঙ্গাপুর", "সিঙ্গাপুরে",
        "ফ্রান্স", "ফ্রান্সে", "প্যারিস",
        "জার্মানি", "জার্মানিতে", "বার্লিন",
        "কানাডা", "কানাডায়", "টরন্টো",
        "অস্ট্রেলিয়া", "অস্ট্রেলিয়ায়", "সিডনি",
        "জাপান", "জাপানে", "টোকিও"
    ]

    INTERNATIONAL_KEYWORDS = [
        "আন্তর্জাতিক", "বিশ্বসংবাদ", "বিশ্বজুড়ে", "বিশ্বজুড়ে", "বিদেশি", "বিদেশে", "বহির্বিশ্ব"
    ]

    def is_international(self, text: str) -> bool:
        """Detects if news takes place outside Bangladesh."""
        text_lower = text.lower()
        has_country = any(c in text_lower for c in self.INTERNATIONAL_COUNTRIES)
        has_intl_kw = any(k in text_lower for k in self.INTERNATIONAL_KEYWORDS)
        return has_country or has_intl_kw

    def match_location(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Scans text for both grassroots Upazilas/Thanas and Districts.
        Returns (district, upazila).
        """
        # First priority: Check all 125 Upazilas with context disambiguation
        for upazila, district in self.upazila_to_district.items():
            if upazila in text:
                if upazila in self.AMBIGUOUS_UPAZILAS:
                    required_context = self.AMBIGUOUS_UPAZILAS[upazila]
                    if not any(req in text for req in required_context):
                        continue
                return district, upazila

        # Second priority: Check district names
        for district in self.districts:
            if district in text:
                return district, None

        return None, None

    def calculate_virality_score(self, item: Dict) -> float:
        """
        Calculates an Organic Reach & Virality Score (0 to 100) based on
        emotional impact, breaking velocity, hyper-local connection, and visual appeal.
        """
        score = 0.0
        title = item.get("title", "")
        summary = item.get("summary", "")
        text = f"{title} {summary}".lower()

        # 1. High-Engagement Topic Weight (up to 35 pts)
        urgent_public_interest = [
            "কোল্ড স্টোরেজ", "আলু", "ধান", "আম", "ন্যায্যমূল্য", "সার", "দাম বৃদ্ধি",
            "সিন্ডিকেট", "তিস্তা", "নদী ভাঙন", "ভাঙন", "বিদ্যুৎ", "গ্যাস", "দুর্নীতি",
            "ঘুষ", "টেন্ডার", "বেকার", "কর্মসংস্থান", "কৃষক", "বন্যা"
        ]
        breaking_shock = [
            "নিহত", "মর্মান্তিক", "সড়ক দুর্ঘটনা", "অগ্নিকাণ্ড", "ভয়াবহ", "খুন", "হত্যা",
            "ডাকাতি", "গ্রেপ্তার", "আটক", "মহাসড়ক অবরোধ", "সংঘর্ষ", "গুলি", "অবরোধ", "উদ্ধার"
        ]
        regional_pride_dev = [
            "মেগা প্রকল্প", "নতুন ট্রেন", "রেলপথ", "বিমানবন্দর", "সেতু", "উদ্বোধন",
            "ইপিজেড", "সাফল্য", "রেকর্ড", "অর্থনৈতিক অঞ্চল", "শিল্প পার্ক"
        ]
        sharp_politics = [
            "হুশিয়ারি", "কড়া বার্তা", "তোলপাড়", "ডিসি", "এসপি", "উপদেষ্টা", "তারেক রহমান", "জামায়াত", "বিএনপি"
        ]

        if any(k in text for k in urgent_public_interest):
            score += 35
        elif any(k in text for k in breaking_shock):
            score += 30
        elif any(k in text for k in regional_pride_dev):
            score += 28
        elif any(k in text for k in sharp_politics):
            score += 24
        elif any(k in text for k in ["সভা অনুষ্ঠিত", "মতবিনিময়", "কমিটি গঠন", "স্মারকলিপি"]):
            score += 5  # Routine events have very low organic reach on Facebook
        else:
            score += 15

        # 2. Hyper-Local Upazila / Thana Factor (up to 20 pts)
        # News from a specific Thana (like Pirgacha, Ulipur, etc.) triggers massive community group shares
        if item.get("upazila"):
            score += 20
        elif any(k in title for k in ["উপজেলা", "থানা", "ইউনিয়ন", "গ্রামে", "মোড়ে", "বাজারে"]):
            score += 15
        else:
            score += 10

        # 3. Real News Image Present (15 pts, but heavily penalize stock clipart)
        img_url = (item.get("image_url") or "").lower()
        if img_url:
            stock_keywords = [
                "handcuff", "illustration", "stock", "clipart", "vector",
                "placeholder", "gavel", "symbol", "default-news", "generic", "logo"
            ]
            if any(sk in img_url for sk in stock_keywords):
                score -= 30  # Strongly deprioritize generic white/stock cliparts
            else:
                score += 15

        # 4. Headline Engagement & Friction (up to 10 pts)
        # Quotes and exact numbers drive high comment debate
        if any(q in title for q in ["‘", "’", "“", "”", '"', "–", "-"]):
            score += 5
        if any(ch.isdigit() for ch in title) or any(ch in title for ch in "০১২৩৪৫৬৭৮৯"):
            score += 5

        # 5. Timeliness / Recency (up to 20 pts)
        pub_str = item.get("published", "")
        if pub_str:
            try:
                pub_dt = parsedate_to_datetime(pub_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                hours_ago = (now - pub_dt).total_seconds() / 3600.0
                if hours_ago <= 3:
                    score += 20
                elif hours_ago <= 8:
                    score += 15
                elif hours_ago <= 24:
                    score += 10
                else:
                    score += 3
            except Exception:
                score += 10
        else:
            score += 10

        # 6. Facebook Viral & Netizen Buzz Factor (up to 40 pts)
        viral_triggers = [
            "ভাইরাল", "ফেসবুকে তোলপাড়", "ফেসবুকে তোলপাড়", "ভিডিও ভাইরাল",
            "সামাজিক যোগাযোগমাধ্যম", "সামাজিক মাধ্যমে", "নেটিজেনদের", "আলোড়ন",
            "আলোড়ন", "ফেসবুক পোস্ট ঘিরে", "ফেসবুকে পোস্ট", "ভিডিও ছড়িয়ে", "ভিডিও ছড়িয়ে পড়ায়", "কমেন্টের ঝড়"
        ]
        if item.get("is_viral") or any(vt in text for vt in viral_triggers):
            score += 40

        return score

    def _parse_single_feed(self, feed_url: str) -> List[Dict]:
        """Parses a single RSS feed fast using requests with a strict 5s timeout."""
        items = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            res = requests.get(feed_url, headers=headers, timeout=5)
            if res.status_code != 200 or len(res.content) < 50:
                return items

            feed = feedparser.parse(res.content)
            default_source = feed.feed.get("title", "অনলাইন ডেস্ক")

            for entry in feed.entries:
                link = entry.get("link", "").strip()
                if not link:
                    continue

                raw_title = self.clean_html(entry.get("title", ""))
                summary = self.clean_html(entry.get("summary", "") or entry.get("description", ""))

                # Extract full content body if present
                content_text = ""
                if "content" in entry and entry["content"]:
                    for c in entry["content"]:
                        if isinstance(c, dict) and "value" in c:
                            content_text += " " + self.clean_html(c["value"])

                full_body = content_text.strip() if len(content_text.strip()) > len(summary) else summary

                # Extract actual publisher source name
                source_title = default_source
                if "source" in entry and isinstance(entry["source"], dict) and entry["source"].get("title"):
                    source_title = entry["source"]["title"]

                # Clean trailing " - Media House" from headline if present
                title = raw_title
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2 and len(parts[1]) < 30:
                        title = parts[0].strip()
                        if not source_title or "Google" in source_title or source_title == "অনলাইন ডেস্ক":
                            source_title = parts[1].strip()

                # Check for Facebook Viral Topics across Whole Bangladesh
                full_text = f"{title} {full_body}"
                text_lower = full_text.lower()
                viral_triggers = [
                    "ভাইরাল", "ফেসবুকে তোলপাড়", "ফেসবুকে তোলপাড়", "ভিডিও ভাইরাল",
                    "সামাজিক যোগাযোগমাধ্যম", "সামাজিক মাধ্যমে", "নেটিজেনদের", "আলোড়ন",
                    "আলোড়ন", "ফেসবুক পোস্ট ঘিরে", "ফেসবুকে পোস্ট", "ভিডিও ছড়িয়ে", "ভিডিও ছড়িয়ে পড়ায়", "কমেন্টের ঝড়"
                ]
                is_viral = any(vt in text_lower for vt in viral_triggers)

                # Filter for location relevance (North Bengal), Whole BD Viral Topics, or International Viral News
                matched_district, matched_upazila = self.match_location(full_text)

                is_intl = False
                if not matched_district and not matched_upazila:
                    is_intl = self.is_international(full_text)

                if matched_district or matched_upazila or is_viral or is_intl:
                    image_url = self.extract_image(entry)
                    if matched_district:
                        assigned_district = matched_district
                    elif is_intl:
                        assigned_district = "আন্তর্জাতিক"
                    elif is_viral:
                        assigned_district = "সারা দেশ"
                    else:
                        assigned_district = "উত্তরবঙ্গ"

                    candidate = {
                        "title": title,
                        "summary": full_body[:2500],
                        "link": link,
                        "district": assigned_district,
                        "upazila": matched_upazila,
                        "image_url": image_url,
                        "source": source_title,
                        "published": entry.get("published", ""),
                        "is_viral": is_viral,
                        "is_international": is_intl,
                        "template": "viral" if (is_viral or is_intl) else "breaking"
                    }
                    candidate["reach_score"] = self.calculate_virality_score(candidate)
                    items.append(candidate)
        except Exception as e:
            logger.debug(f"Feed error for {feed_url}: {e}")
        return items

    def fetch_candidates(self) -> List[Dict]:
        """Scans all national, regional, and upazila feeds in parallel."""
        candidates = []
        seen_links = set()

        logger.info(f"Scanning {len(RSS_FEEDS)} master news feeds across Bangladesh & North Bengal Upazilas...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(self._parse_single_feed, RSS_FEEDS)
            for feed_items in results:
                for item in feed_items:
                    link = item["link"]
                    if link not in seen_links:
                        seen_links.add(link)
                        candidates.append(item)

        logger.info(f"Total North Bengal candidate news collected: {len(candidates)}")
        return candidates
