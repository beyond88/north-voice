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

    def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """
        Uses Gemini to filter, choose template, generate Bengali headline and Facebook caption.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")

        if not self.client:
            # Fallback heuristic if no Gemini API key is configured yet
            return {
                "is_relevant": True,
                "template": "breaking" if any(w in title for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন"]) else "general",
                "headline_html": f"{title}",
                "sub_headline": f"{district} বার্তা",
                "speaker_name": "",
                "speaker_title": "",
                "fb_caption": f"📌 {title}\n\nবিস্তারিত: {summary}\n\nসূত্র: {source}\n\n#NorthVoice #উত্তরবঙ্গ #{district} #NorthBengalNews",
                "district": district
            }

        prompt = f"""
তুমি 'North Voice' (উত্তরবঙ্গের জনপ্রিয় ডিজিটাল নিউজ পেইজ)-এর চিফ এডিটর।
নিচের সংবাদের তথ্য বিশ্লেষণ করে আকর্ষণীয় ফটোকার্ডের কনটেন্ট ও ফেসবুক পোস্ট তৈরি করো।

সংবাদের তথ্য:
- শিরোনাম: {title}
- সারসংক্ষেপ: {summary}
- মূল এলাকা: {district}
- সূত্র: {source}

তোমার করণীয়:
1. সংবাদের গুরুত্ব অনুযায়ী টেমপ্লেট বেছে নাও:
   - 'breaking': দুর্ঘটনা, অগ্নিকাণ্ড, ক্রাইম, অভিযান, হঠাৎ কোনো গুরুত্বপূর্ণ ঘোষণা বা সাধারণ বড় সংবাদ।
   - 'quote': যদি কোনো ব্যক্তি, নেতা বা কর্মকর্তার উক্তি বা বক্তব্য থাকে।
   - 'general': উন্নয়ন, কৃষি, পর্যটন, শিক্ষা, সংস্কৃতি বা সাধারণ প্রতিবেদন।
2. ফটোকার্ডের জন্য অত্যন্ত আকর্ষণীয়, সংক্ষিপ্ত (২-৩ লাইন) এবং সত্যনিষ্ঠ বাংলা হেডলাইন তৈরি করো।
   সবচেয়ে গুরুত্বপূর্ণ শব্দগুচ্ছকে <span class="highlight">শব্দ</span> ট্যাগ দিয়ে ঘিরে দাও যাতে তা আলাদা রঙে ফোকাস পায়।
3. ফেসবুক পোস্টের জন্য একটি সুন্দর ক্যাপশন বানাও যাতে থাকবে: মূল বিষয়বস্তু, প্রাসঙ্গিক হ্যাশট্যাগ (#NorthVoice #উত্তরবঙ্গ #{district} ইত্যাদি) এবং সূত্রের কৃতজ্ঞতা।

নিচের JSON ফরম্যাটে উত্তর প্রদান করো (অন্য কোনো টেক্সট বা মার্কডাউন ছাড়া):
{{
  "is_relevant": true,
  "template": "breaking",
  "headline_html": "বগুড়ায় মহাসড়কে <span class='highlight'>তীব্র যানজট</span>, ভোগান্তিতে হাজারো যাত্রী",
  "sub_headline": "বগুড়া বার্তা",
  "speaker_name": "",
  "speaker_title": "",
  "fb_caption": "ক্যাপশন টেক্সট...",
  "district": "{district}"
}}
"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            data = json.loads(response.text)
            logger.info(f"AI Editor selected template: {data.get('template')} for '{title[:30]}...'")
            return data
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Falling back to default editor.")
            return {
                "is_relevant": True,
                "template": "breaking",
                "headline_html": title,
                "sub_headline": f"{district} বার্তা",
                "speaker_name": "",
                "speaker_title": "",
                "fb_caption": f"{title}\n\nসূত্র: {source}\n\n#NorthVoice #উত্তরবঙ্গ",
                "district": district
            }
