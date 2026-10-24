import re
import logging
from typing import List, Dict, Optional
import feedparser
from bs4 import BeautifulSoup
from src.config import RSS_FEEDS, NORTH_BENGAL_DISTRICTS

logger = logging.getLogger(__name__)

class NewsHunter:
    def __init__(self):
        self.districts = NORTH_BENGAL_DISTRICTS

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
                if "url" in media:
                    return media["url"]

        # 2. Enclosures
        if "enclosures" in entry and entry["enclosures"]:
            for enc in entry["enclosures"]:
                if "href" in enc and ("image" in enc.get("type", "") or enc.get("href", "").endswith((".jpg", ".png", ".jpeg", ".webp"))):
                    return enc["href"]

        # 3. Media thumbnail
        if "media_thumbnail" in entry and entry["media_thumbnail"]:
            return entry["media_thumbnail"][0].get("url")

        # 4. Search within HTML summary / description
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary:
            soup = BeautifulSoup(summary, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                return img["src"]

        return None

    def match_district(self, text: str) -> Optional[str]:
        """Checks if any North Bengal district is mentioned in the text."""
        for district in self.districts:
            if district in text:
                return district
        return None

    def fetch_candidates(self) -> List[Dict]:
        """Scans all configured feeds and yields North Bengal news items."""
        candidates = []
        seen_links = set()

        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                default_source = feed.feed.get("title", "অনলাইন ডেস্ক")

                for entry in feed.entries:
                    link = entry.get("link", "").strip()
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)

                    raw_title = self.clean_html(entry.get("title", ""))
                    summary = self.clean_html(entry.get("summary", "") or entry.get("description", ""))

                    # Extract full content body if available from RSS
                    content_text = ""
                    if "content" in entry and entry["content"]:
                        for c in entry["content"]:
                            if isinstance(c, dict) and "value" in c:
                                content_text += " " + self.clean_html(c["value"])

                    full_body = content_text.strip() if len(content_text.strip()) > len(summary) else summary

                    # Extract actual media house / TV channel source name
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

                    # Filter for North Bengal relevance
                    full_text = f"{title} {full_body}"
                    matched_district = self.match_district(full_text)

                    if matched_district:
                        image_url = self.extract_image(entry)
                        candidates.append({
                            "title": title,
                            "summary": full_body[:2500],
                            "link": link,
                            "district": matched_district,
                            "image_url": image_url,
                            "source": source_title,
                            "published": entry.get("published", "")
                        })
            except Exception as e:
                logger.error(f"Error parsing feed {feed_url}: {e}")

        logger.info(f"Total North Bengal news candidates collected: {len(candidates)}")
        return candidates
