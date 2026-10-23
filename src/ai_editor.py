import json
import logging
from typing import Dict, Optional
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, BRAND_NAME, BRAND_HANDLE

logger = logging.getLogger(__name__)

class AIEditor:
    def __init__(self):
        self.client = None
        if GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Initialized Google Gemini AI Editor successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found. Running with rule-based fallback editor.")

    def fallback_analyze(self, title: str, summary: str, source: str, district: str) -> Dict:
        """Intelligently routes news to all 4 templates even in fallback mode."""
        full_text = f"{title} {summary}"

        # 1. Breaking (Red Banner)
        if any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন", "ডাকাতি", "ধর্ষন", "খুন", "অবরোধ"]):
            template = "breaking"
        # 2. Quote Card (Dark Editorial)
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি করেন", "হুশিয়ারি", "উক্তি", "ঘোষণা"]):
            template = "quote"
        # 3. Inqilab Style (Politics, bilateral, governance)
        elif any(w in full_text for w in ["রাজনীতি", "সীমান্ত", "তিস্তা", "নির্বাচন", "বিএনপি", "জামায়াত", "সরকার", "আন্দোলন"]):
            template = "inqilab_style"
        # 4. General (Agriculture, economics, feature)
        else:
            template = "general"

        return {
            "is_relevant": True,
            "template": template,
            "headline_html": title,
            "sub_headline": f"{district} বার্তা",
            "speaker_name": "",
            "speaker_title": "",
            "fb_caption": f"📌 {title}\n\n{summary[:250]}...\n\nসূত্র: {source}\n\n#NorthVoice #উত্তরবঙ্গ #{district} #NorthBengalNews",
            "district": district
        }

    def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """
        Uses Gemini 3.8 Flash to analyze news and pick the optimal template out of all 4 designs.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")

        if not self.client:
            return self.fallback_analyze(title, summary, source, district)

        prompt = f"""
তুমি 'North Voice' (উত্তরবঙ্গের জনপ্রিয় ডিজিটাল নিউজ পেইজ)-এর চিফ এডিটর।
নিচের সংবাদের তথ্য বিশ্লেষণ করে সবচেয়ে মানানসই ফটোকার্ডের কনটেন্ট ও ফেসবুক পোস্ট তৈরি করো।

সংবাদের তথ্য:
- শিরোনাম: {title}
- সারসংক্ষেপ: {summary}
- মূল এলাকা: {district}
- সূত্র: {source}

তোমার করণীয়:
১. সংবাদের বিষয়বস্তুর ধরন অনুযায়ী নিচের ৪টি ডিজাইনের মধ্যে সবচেয়ে পারফেক্ট টেমপ্লেটটি নির্বাচন করো:
   - 'breaking': দুর্ঘটনা, অগ্নিকাণ্ড, ক্রাইম, অভিযান, মৃত্যু, মহাসড়ক অবরোধ বা হঠাৎ ঘটা ব্রেকিং নিউজ (Star News Red Banner Style)।
   - 'quote': কোনো নেতা, কর্মকর্তা, ডিসি, এসপি, মন্ত্রী বা বিশিষ্ট ব্যক্তির সরাসরি উক্তি, মন্তব্য বা কড়া বক্তব্য (Rongo Graph / Dark Quote Card Style)।
   - 'general': কৃষি, উন্নয়ন, অর্থনীতি, ফসল (আম, লিচু, আলু, ধান), নদী, দ্রব্যমূল্য, শিক্ষা, পর্যটন বা সাধারণ ফিচার সংবাদ (Channel 24 Cream Paper Style)।
   - 'inqilab_style': রাজনীতি, জাতীয় বনাম আঞ্চলিক তুলনা, তিস্তা বা সীমান্ত ইস্যু, নীতি নির্ধারণ, রাজনৈতিক বিতর্ক বা পরিবর্তনের খবর (Daily Inqilab Style)।

২. ফটোকার্ডের জন্য অত্যন্ত আকর্ষণীয়, সংক্ষিপ্ত (২-৩ লাইন) এবং পাঠযোগ্য বাংলা হেডলাইন তৈরি করো।
   সবচেয়ে গুরুত্বপূর্ণ ১-২টি শব্দগুচ্ছকে <span class="highlight">শব্দ</span> ট্যাগ দিয়ে ঘিরে দাও যাতে তা আলাদা রঙে উজ্জ্বল ফোকাস পায়।

৩. টেমপ্লেট যদি 'quote' হয়, তবে সংবাদের ভেতর থেকে বক্তার নাম (speaker_name) এবং পদবি (speaker_title) আলাদা করো।

৪. ফেসবুক পোস্টের জন্য একটি চমৎকার পূর্ণাঙ্গ ক্যাপশন বানাও যাতে থাকবে: মূল বিষয়বস্তু, প্রাসঙ্গিক হ্যাশট্যাগ (#NorthVoice #উত্তরবঙ্গ #{district} ইত্যাদি) এবং সূত্রের কৃতজ্ঞতা।

নিচের JSON ফরম্যাটে সরাসরি উত্তর প্রদান করো (অন্য কোনো টেক্সট বা ব্যাকটিক ছাড়া):
{{
  "is_relevant": true,
  "template": "breaking" | "quote" | "general" | "inqilab_style",
  "headline_html": "হেডলাইন টেক্সট <span class='highlight'>হাইলাইট</span> সহ...",
  "sub_headline": "সাব-হেডলাইন (প্রযোজ্য ক্ষেত্রে)",
  "speaker_name": "বক্তার নাম (শুধুমাত্র quote টেমপ্লেটে)",
  "speaker_title": "বক্তার পদবি (শুধুমাত্র quote টেমপ্লেটে)",
  "fb_caption": "ফেসবুক ক্যাপশন টেক্সট...",
  "district": "{district}"
}}
"""

        try:
            response = self.client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            data = json.loads(response.text)
            logger.info(f"AI Editor selected template: '{data.get('template')}' for '{title[:30]}...'")
            return data
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Using intelligent fallback.")
            return self.fallback_analyze(title, summary, source, district)
