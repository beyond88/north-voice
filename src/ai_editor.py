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
        """Intelligently routes news to all 4 templates without emojis/icons in clean journalistic style."""
        full_text = f"{title} {summary}"

        # 1. Breaking (Red Banner)
        if any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন", "ডাকাতি", "ধর্ষন", "খুন", "অবরোধ"]):
            template = "breaking"
            header_badge = f"ব্রেকিং নিউজ | {district}"
            cta_question = f"এ বিষয়ে আপনার এলাকার সার্বিক পরিস্থিতি সম্পর্কে আপনার মতামত কমেন্টে জানান।"
        # 2. Quote Card (Dark Editorial)
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি করেন", "হুশিয়ারি", "উক্তি", "ঘোষণা"]):
            template = "quote"
            header_badge = f"বিশেষ বক্তব্য | {district}"
            cta_question = f"বক্তার এই বক্তব্যের সাথে আপনি কি একমত? আপনার যুক্তিযুক্ত মতামত কমেন্টে তুলে ধরুন।"
        # 3. Inqilab Style (Politics, bilateral, governance)
        elif any(w in full_text for w in ["রাজনীতি", "সীমান্ত", "তিস্তা", "নির্বাচন", "বিএনপি", "জামায়াত", "সরকার", "আন্দোলন"]):
            template = "inqilab_style"
            header_badge = f"রাজনীতি ও সমসাময়িক | {district}"
            cta_question = f"এই সমসাময়িক প্রেক্ষাপট নিয়ে আপনার মূল্যায়ন কী? কমেন্টে আলোচনা করুন।"
        # 4. General (Agriculture, economics, feature)
        else:
            template = "general"
            header_badge = f"উত্তরবঙ্গ সমাচার | {district}"
            cta_question = f"উত্তরবঙ্গের সামগ্রিক উন্নয়নে এমন উদ্যোগ কতটা গুরুত্বপূর্ণ বলে আপনি মনে করেন? আপনার অভিজ্ঞতা শেয়ার করুন।"

        caption = (
            f"{header_badge}\n\n"
            f"{title}\n\n"
            f"{summary[:300]}...\n\n"
            f"আপনার মতামত:\n"
            f"{cta_question}\n\n"
            f"তথ্যসূত্র: {source}\n\n"
            f"#NorthVoice #উত্তরবঙ্গ #{district} #NorthBengal #BangladeshNews"
        )

        return {
            "is_relevant": True,
            "template": template,
            "headline_html": title,
            "sub_headline": f"{district} বার্তা",
            "speaker_name": "",
            "speaker_title": "",
            "fb_caption": caption,
            "district": district
        }

    def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """
        Uses Gemini 3.8 Flash to analyze news, pick the optimal template, and write clean journalistic captions without any emojis/icons.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")

        if not self.client:
            return self.fallback_analyze(title, summary, source, district)

        prompt = f"""
তুমি 'North Voice' (উত্তরবঙ্গের দায়িত্বশীল ও জনপ্রিয় ডিজিটাল নিউজ পেইজ)-এর চিফ এডিটর।
নিচের সংবাদের তথ্য বিশ্লেষণ করে সবচেয়ে মানানসই ফটোকার্ডের কনটেন্ট ও পেশাদার প্রিন্ট/টিভি সাংবাদিকতার মানসম্পন্ন বাংলা ফেসবুক পোস্ট তৈরি করো।

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

৪. ফেসবুক ক্যাপশন লেখার ক্ষেত্রে কঠোর নিয়মাবলী:
   ক. অত্যন্ত জরুরি: ক্যাপশনের কোথাও ভুলেও কোনো প্রকার ইমোজি বা আইকন (যেমন: 🚨, 🔹, 💬, 👉, 📰, 📌 ইত্যাদি) ব্যবহার করবে না। এটি সম্পূর্ণ নিষিদ্ধ। দেশের প্রথম সারির শীর্ষ দৈনিকের মতো শতভাগ পরিচ্ছন্ন ও পেশাদার ভাষায় লিখবে।
   খ. শুরুতে মার্জিত একটি হেডার থাকবে: 'ব্রেকিং নিউজ | {district}' অথবা 'উত্তরবঙ্গ সমাচার | {district}'
   গ. শিরোনাম এবং সংবাদের মূল ঘটনা সহজ-সরল ভাষায় ২-৩ বাক্যে তুলে ধরবে যাতে পাঠক দ্রুত বুঝতে পারে।
   ঘ. কমেন্টে আলোচনা বাড়ানোর জন্য প্রাসঙ্গিক ১টি সুনির্দিষ্ট চিন্তাশীল প্রশ্ন রাখবে: 'আপনার মতামত: [প্রশ্ন]'
   ঙ. তথ্যের সূত্র: 'তথ্যসূত্র: {source}'
   চ. সার্চ র‍্যাংকিংয়ের জন্য হ্যাশট্যাগ: #NorthVoice #উত্তরবঙ্গ #{district} #NorthBengal #BangladeshNews

নিচের JSON ফরম্যাটে সরাসরি উত্তর প্রদান করো (অন্য কোনো টেক্সট বা ব্যাকটিক ছাড়া):
{{
  "is_relevant": true,
  "template": "breaking" | "quote" | "general" | "inqilab_style",
  "headline_html": "হেডলাইন টেক্সট <span class='highlight'>হাইলাইট</span> সহ...",
  "sub_headline": "সাব-হেডলাইন (প্রযোজ্য ক্ষেত্রে)",
  "speaker_name": "বক্তার নাম (শুধুমাত্র quote টেমপ্লেটে)",
  "speaker_title": "বক্তার পদবি (শুধুমাত্র quote টেমপ্লেটে)",
  "fb_caption": "সম্পূর্ণ পরিচ্ছন্ন ও শতভাগ ইমোজিহীন প্রফেশনাল ফেসবুক ক্যাপশন...",
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
