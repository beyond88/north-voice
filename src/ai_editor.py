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
            f"{summary[:500]}...\n\n"
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
        Uses Gemini 3.8 Flash to analyze news, intelligently decide between deep long-form
        journalism vs crisp breaking reports, pick the optimal visual template,
        and write 100% icon-free professional Bengali broadsheet copy.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")

        if not self.client:
            return self.fallback_analyze(title, summary, source, district)

        prompt = f"""
তুমি 'North Voice' (উত্তরবঙ্গের দায়িত্বশীল ও শীর্ষস্থানীয় ডিজিটাল সংবাদ মাধ্যম)-এর প্রধান বার্তা সম্পাদক (Chief News Editor)।
তোমার কাজ হলো নিচের সংবাদের তথ্য বিশ্লেষণ করে প্রথম সারির জাতীয় দৈনিকের (যেমন: প্রথম আলো, সমকাল বা ডেইলি স্টার) মতো উচ্চমানের, বস্তুনিষ্ঠ এবং মানবীয় সাংবাদিকতার মানসম্পন্ন বাংলা কনটেন্ট তৈরি করা। লেখাটি যেন কোনোভাবেই রোবোটিক বা কৃত্রিম (AI-generated) মনে না হয়।

সংবাদের তথ্য:
- শিরোনাম: {title}
- মূল বিবরণ ও তথ্যসমূহ: {summary}
- মূল এলাকা: {district}
- সূত্র: {source}

তোমার করণীয় ও সম্পাদকীয় নির্দেশিকা:

১. সংবাদের গভীরতা অনুযায়ী কাঠামোগত সিদ্ধান্ত (Dynamic Length & Structuring):
   ক. দীর্ঘ ও বিশ্লেষণধর্মী প্রতিবেদন (In-depth Long-form Report):
      - ক্ষেত্র: মেগা প্রকল্প, আঞ্চলিক উন্নয়ন, অর্থনীতি ও বাণিজ্য, কৃষি ও ফলন (আম, লিচু, আলু, ধান), তিস্তা বা সীমান্ত ইস্যু, নদী রক্ষা, শিল্পায়ন, শিক্ষা, নীতি-নির্ধারণ, বাজেট বা গুরুত্বপূর্ণ সমসাময়িক জাতীয়-আঞ্চলিক রাজনীতি।
      - ফরম্যাট: সংবাদের গভীরতা অনুযায়ী ৩ থেকে ৫টি পরিচ্ছন্ন অনুচ্ছেদে বিস্তারিত প্রতিবেদন লিখবে।
      - সাব-হেডলাইন ব্যবহার: বিষয়বস্তুর ভিন্নতা অনুযায়ী ভেতরে প্রাসঙ্গিক ও অর্থবহ সাব-হেডলাইন (Sub-headings) ব্যবহার করবে। যেমন:
        'উন্নয়নে নতুন সম্ভাবনা :'
        'বাস্তব চ্যালেঞ্জ ও সংকট :'
        'বিশেষজ্ঞ ও অংশীজনদের মতামত :'
        'চাষীদের প্রত্যাশা ও বাজার পরিস্থিতি :'
      - অনুচ্ছেদে সংবাদের বিস্তারিত তথ্য, সংখ্যা (Data), উক্তি (Quotes) ও প্রেক্ষাপট তুলে ধরবে।
      - মোবাইল স্ক্রিনে স্বাচ্ছন্দ্যে পড়ার সুবিধার্থে প্রতি অনুচ্ছেদ ২-৩ বাক্যে সীমাবদ্ধ রাখবে এবং প্রতিটি অনুচ্ছেদের পর একটি ফাঁকা লাইন (Double newline) দেবে।

   খ. সংক্ষিপ্ত ও সরাসরি ব্রেকিং প্রতিবেদন (Crisp Breaking Report):
      - ক্ষেত্র: তাৎক্ষণিক সড়ক দুর্ঘটনা, অগ্নিকাণ্ড, আকস্মিক অপরাধ, গ্রেপ্তার বা অভিযান, মহাসড়ক অবরোধ ইত্যাদি।
      - ফরম্যাট: কোনো বাহুল্য ছাড়াই অত্যন্ত দ্রুত ও ধারালো ২-৩ অনুচ্ছেদে মূল তথ্যগুলো (কী ঘটেছে, কোথায়, হতাহত/ক্ষয়ক্ষতি, প্রশাসনের তাৎক্ষণিক ব্যবস্থা) তুলে ধরবে।

২. কঠোরভাবে নিষিদ্ধ বিষয়সমূহ (Strict Negative Rules):
   - কোনো প্রকার ইমোজি বা আইকন (যেমন: 🚨, 👉, 🔹, 💬, 📰, 📌, 💥 ইত্যাদি) ব্যবহার করা সম্পূর্ণরূপে নিষিদ্ধ। ক্যাপশনের কোনো জায়গায় ভুলেও কোনো আইকন ব্যবহার করবে না।
   - কোনো চটুল বা এআই-ক্লিশে বাক্য ব্যবহার করা যাবে না (যেমন: 'আসুন জেনে নেই', 'চলুন দেখে নেওয়া যাক', 'আমাদের সাথেই থাকুন', 'এটি নিঃসন্দেহে ইতিবাচক দিক', 'পাঠক বন্ধুরা', 'আলোচনার ঝড় উঠেছে' ইত্যাদি)।
   - কোনো নাটকীয় বা কৃত্রিম অতিরঞ্জন করবে না। কণ্ঠস্বর হবে তথ্যভিত্তিক, মার্জিত, নিরপেক্ষ ও ভারসাম্যপূর্ণ।

৩. ফেসবুক ক্যাপশনের সার্বিক বিন্যাস (fb_caption):
   [হেডার: 'ব্রেকিং নিউজ | {district}' অথবা 'উত্তরবঙ্গ সমাচার | {district}' অথবা 'বিশেষ প্রতিবেদন | {district}']

   [শিরোনাম ও প্রেক্ষাপট - মূল ঘটনা ২-৩ বাক্যে]

   [মূল বিবরণ - দীর্ঘ সংবাদের ক্ষেত্রে প্রয়োজন অনুযায়ী প্রাসঙ্গিক সাব-হেডলাইনসহ ২ থেকে ৪টি প্যারাগ্রাফ, প্রতিটি প্যারার মাঝে ফাঁকা লাইন]

   আপনার মতামত:
   [পাঠকদের সুচিন্তিত মতামত ও অভিজ্ঞতা জানতে ১টি দায়িত্বশীল ও প্রাসঙ্গিক প্রশ্ন]

   তথ্যসূত্র: {source}

   #NorthVoice #উত্তরবঙ্গ #{district} #NorthBengal #BangladeshNews

৪. ফটোকার্ডের জন্য টেমপ্লেট নির্বাচন (template):
   - 'breaking': দুর্ঘটনা, অগ্নিকাণ্ড, ক্রাইম, অভিযান, হঠাৎ ঘটা ব্রেকিং নিউজ (Star News Red Banner Style)।
   - 'quote': কোনো বিশিষ্ট ব্যক্তি, রাজনীতিবিদ, প্রশাসক বা কর্মকর্তার সরাসরি বক্তব্য বা মন্তব্য (Rongo Graph Dark Quote Card Style)।
   - 'general': কৃষি, উন্নয়ন, অর্থনীতি, ফসল, নদী, পর্যটন বা সাধারণ সমাচার (Channel 24 Cream Paper Style)।
   - 'inqilab_style': রাজনীতি, তিস্তা/সীমান্ত চুক্তি, শাসনব্যবস্থা, জাতীয় বনাম আঞ্চলিক তুলনা (Daily Inqilab Style)।

৫. ফটোকার্ডের হেডলাইন (headline_html):
   - ফটোকার্ডে ব্যবহারের জন্য অত্যন্ত আকর্ষণীয়, সংক্ষিপ্ত (২-৩ লাইন) এবং সহজে পড়ার উপযোগী হেডলাইন তৈরি করো।
   - সবচেয়ে গুরুত্বপূর্ণ মূল শব্দগুচ্ছকে <span class="highlight">শব্দ</span> দিয়ে মার্ক করবে।
   - টেমপ্লেট 'quote' হলে সংবাদের ভেতর থেকে বক্তার নাম (speaker_name) ও পদবি (speaker_title) আলাদা করবে।

নিচের JSON ফরম্যাটে সরাসরি উত্তর প্রদান করো (অন্য কোনো টেক্সট বা মার্কডাউন ব্যাকটিক ছাড়া):
{{
  "is_relevant": true,
  "template": "breaking" | "quote" | "general" | "inqilab_style",
  "headline_html": "হেডলাইন টেক্সট <span class='highlight'>হাইলাইট</span> সহ...",
  "sub_headline": "সাব-হেডলাইন (প্রযোজ্য ক্ষেত্রে)",
  "speaker_name": "বক্তার নাম (শুধুমাত্র quote টেমপ্লেটে)",
  "speaker_title": "বক্তার পদবি (শুধুমাত্র quote টেমপ্লেটে)",
  "fb_caption": "সম্পূর্ণ পরিচ্ছন্ন, সাব-হেডলাইন ও সঠিক প্যারাগ্রাফ স্পেসিং সহ শতভাগ প্রফেশনাল ফেসবুক ক্যাপশন...",
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
            raw_text = response.text.strip()
            # If wrapped in ```json ... ```, strip it
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            data = json.loads(raw_text)
            logger.info(f"AI Editor selected template: '{data.get('template')}' for '{title[:30]}...'")
            return data
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Using intelligent fallback.")
            return self.fallback_analyze(title, summary, source, district)
