import os
import time
import base64
import logging
from datetime import datetime
from typing import Dict, Optional
import requests
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# Bengali Digits and Months
BANGLA_DIGITS = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}
BANGLA_MONTHS = {
    1: 'জানুয়ারি', 2: 'ফেব্রুয়ারি', 3: 'মার্চ', 4: 'এপ্রিল',
    5: 'মে', 6: 'জুন', 7: 'জুলাই', 8: 'আগস্ট',
    9: 'সেপ্টেম্বর', 10: 'অক্টোবর', 11: 'নভেম্বর', 12: 'ডিসেম্বর'
}

def to_bangla_number(num: int) -> str:
    return "".join(BANGLA_DIGITS.get(d, d) for d in str(num))

def get_bangla_date() -> str:
    now = datetime.now()
    day = to_bangla_number(now.day)
    month = BANGLA_MONTHS[now.month]
    year = to_bangla_number(now.year)
    return f"{day} {month} {year}"

def to_data_uri(file_path: str) -> str:
    """Converts a local image file to a base64 Data URI so it renders flawlessly in headless browser."""
    if not file_path or not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    mime = f"image/{ext}" if ext in ("jpeg", "png", "webp", "gif", "svg+xml") else "image/jpeg"
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

class CardGenerator:
    def __init__(self, template_dir: str = "templates", assets_dir: str = "assets/branding"):
        self.template_dir = os.path.abspath(template_dir)
        self.assets_dir = os.path.abspath(assets_dir)
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

        # Default fallback image
        self.logo_path = os.path.join(self.assets_dir, "logo.png")

    def download_image(self, url: str, output_path: str) -> bool:
        """Downloads external news image with proper user-agent headers."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
        return False

    def generate_card(self, news_data: Dict, output_dir: str = "output") -> Optional[str]:
        """
        Renders the photocard based on selected template and returns local image path.
        """
        os.makedirs(output_dir, exist_ok=True)
        template_name = news_data.get("template", "breaking")
        if template_name not in ("breaking", "quote", "general"):
            template_name = "breaking"

        template_file = f"{template_name}.html"
        try:
            template = self.env.get_template(template_file)
        except Exception as e:
            logger.error(f"Template not found: {template_file}, error: {e}")
            template = self.env.get_template("breaking.html")

        # Handle image
        timestamp = int(time.time())
        temp_img_path = os.path.join(output_dir, f"temp_news_{timestamp}.jpg")
        image_url = news_data.get("image_url")
        final_image_path = None

        if image_url and self.download_image(image_url, temp_img_path):
            final_image_path = os.path.abspath(temp_img_path)
        else:
            # Fallback to branding logo or cover background
            final_image_path = os.path.abspath(self.logo_path)

        logo_abs_path = os.path.abspath(self.logo_path)

        render_data = {
            "headline_html": news_data.get("headline_html", news_data.get("title", "")),
            "sub_headline": news_data.get("sub_headline", ""),
            "district": news_data.get("district", "উত্তরবঙ্গ"),
            "speaker_name": news_data.get("speaker_name", ""),
            "speaker_title": news_data.get("speaker_title", ""),
            "source": news_data.get("source", "অনলাইন ডেস্ক"),
            "bangla_date": get_bangla_date(),
            "image_path": to_data_uri(final_image_path),
            "logo_path": to_data_uri(logo_abs_path)
        }

        html_content = template.render(**render_data)
        out_image_path = os.path.abspath(os.path.join(output_dir, f"card_{template_name}_{timestamp}.png"))

        # Render using Playwright headless Chromium
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
                page.set_content(html_content, wait_until="networkidle")
                page.screenshot(path=out_image_path)
                browser.close()

            logger.info(f"Photocard successfully generated at: {out_image_path}")
            return out_image_path
        except Exception as e:
            logger.error(f"Playwright card generation failed: {e}")
            return None
