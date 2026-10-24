import json
import time
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

    @staticmethod
    def format_clean_story(text: str, max_chars: int = 900) -> str:
        """
        Formats Bengali story into clean, complete sentences and well-spaced paragraphs.
        Never cuts sentences in the middle. Always ends on a proper sentence boundary (।).
        """
        if not text:
            return ""

        import re
        clean_text = " ".join(text.split())
        raw_sentences = re.split(r'(?<=[।?!])\s+', clean_text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        if not sentences:
            return clean_text[:max_chars]

        paragraphs = []
        current_para = []
        char_count = 0

        for s in sentences:
            if char_count + len(s) > max_chars and paragraphs:
                break
            current_para.append(s)
            char_count += len(s)
            # Group 2 sentences per paragraph for mobile dwell-time rhythm
            if len(current_para) >= 2:
                paragraphs.append(" ".join(current_para))
                current_para = []

        if current_para:
            paragraphs.append(" ".join(current_para))

        return "\n\n".join(paragraphs)

    def fallback_analyze(self, title: str, summary: str, source: str, district: str, upazila: Optional[str] = None, is_viral: bool = False) -> Dict:
        """Intelligently routes news to templates without emojis/icons in clean journalistic style."""
        full_text = f"{title} {summary}"
        loc_display = f"{upazila}, {district}" if upazila else district
        subhead = f"{upazila} বার্তা" if upazila else (f"{district} বার্তা" if district != "সারা দেশ" else "সারা দেশ")

        # 1. Facebook Viral Topics (Yellow Badge + Dark Slate Card - Whole Bangladesh)
        viral_triggers = ["ভাইরাল", "তোলপাড়", "তোলপাড়", "আলোড়ন", "সামাজিক যোগাযোগমাধ্যম", "নেটিজেনদের", "ভিডিও ছড়িয়ে"]
        if is_viral or any(vt in full_text.lower() for vt in viral_triggers):
            template = "viral"
            header_badge = f"ভাইরাল সংবাদ | {loc_display}"
            cta_question = f"সামাজিক যোগাযোগমাধ্যমে তোলপাড় সৃষ্টি করা এই ঘটনাটিকে আপনি কীভাবে দেখছেন? আপনার সুচিন্তিত মতামত কমেন্টে জানান।"
        # 2. Quote Card (Dark Editorial)
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি করেন", "হুশিয়ারি", "উক্তি", "ঘোষণা"]):
            template = "quote"
            header_badge = f"বিশেষ বক্তব্য | {loc_display}"
            cta_question = f"বক্তার এই বক্তব্যের সাথে আপনি কি একমত? আপনার যুক্তিযুক্ত মতামত কমেন্টে তুলে ধরুন।"
        # 3. Inqilab Style (Politics, bilateral, governance)
        elif any(w in full_text for w in ["রাজনীতি", "সীমান্ত", "তিস্তা", "নির্বাচন", "বিএনপি", "জামায়াত", "সরকার", "আন্দোলন"]):
            template = "inqilab_style"
            header_badge = f"রাজনীতি ও সমসাময়িক | {loc_display}"
            cta_question = f"এই সমসাময়িক প্রেক্ষাপট নিয়ে আপনার মূল্যায়ন কী? কমেন্টে আলোচনা করুন।"
        # 4. Signature Crimson Photocard (Breaking, Development, Agriculture, Crime, Human Interest)
        else:
            template = "breaking"
            if any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন", "ডাকাতি", "খুন", "অবরোধ"]):
                header_badge = f"ব্রেকিং নিউজ | {loc_display}"
                cta_question = f"এ বিষয়ে আপনার এলাকার সার্বিক পরিস্থিতি সম্পর্কে আপনার মতামত কমেন্টে জানান।"
            else:
                header_badge = f"উত্তরবঙ্গ সমাচার | {loc_display}"
                cta_question = f"উত্তরবঙ্গের সামগ্রিক উন্নয়নে এমন উদ্যোগ কতটা গুরুত্বপূর্ণ বলে আপনি মনে করেন? আপনার অভিজ্ঞতা শেয়ার করুন।"

        formatted_body = self.format_clean_story(summary, max_chars=900)
        if not formatted_body:
            formatted_body = title

        upazila_tag = f"#{upazila} " if upazila else ""
        caption = (
            f"{header_badge}\n\n"
            f"{title}\n\n"
            f"{formatted_body}\n\n"
            f"আপনার মতামত:\n"
            f"{cta_question}\n\n"
            f"তথ্যসূত্র: {source}\n\n"
            f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#NorthBengal #BangladeshNews"
        )

        return {
            "is_relevant": True,
            "template": template,
            "headline_html": title,
            "sub_headline": subhead,
            "speaker_name": "",
            "speaker_title": "",
            "fb_caption": caption,
            "district": district,
            "upazila": upazila
        }

    def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """
        Uses Gemini 3.8 Flash to analyze news, intelligently decide between deep long-form
        journalism vs crisp breaking reports, pick the optimal visual template,
        and write 100% human-grade, zero-plagiarism broadsheet copy.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")
        upazila = news_item.get("upazila")
        is_viral = news_item.get("is_viral", False)
        loc_display = f"{upazila}, {district}" if upazila else district

        if not self.client:
            return self.fallback_analyze(title, summary, source, district, upazila, is_viral=is_viral)

        prompt = f"""
তুমি 'North Voice' (উত্তরবঙ্গের শীর্ষস্থানীয় ও দায়িত্বশীল ডিজিটাল সংবাদ মাধ্যম)-এর প্রধান বার্তা সম্পাদক (Chief News Editor)।
তোমার মূল দায়িত্ব: নিচে প্রদত্ত সংবাদের তথ্যসমূহকে ভিত্তি করে প্রথম সারির জাতীয় দৈনিকের (প্রথম আলো, সমকাল বা ডেইলি স্টার) মতো শতভাগ মানবীয়, প্রাণবন্ত, মৌলিক ও বস্তুনিষ্ঠ সাংবাদিকতায় ফেসবুক পোস্ট লেখা।

অত্যন্ত গুরুত্বপূর্ণ শর্তাবলি (Humanization & Zero-Plagiarism Guidelines):
১. শতভাগ মৌলিক পুনর্লিখন (Zero-Plagiarism Paraphrase):
   - মূল সংবাদের কোনো বাক্য বা ৪-৫ শব্দের বেশি অংশ হুবহু কপি বা পেস্ট করা সম্পূর্ণ নিষিদ্ধ।
   - তথ্য ও প্রেক্ষাপট ঠিক রেখে বাক্য গঠন, শব্দচয়ন ও বর্ণনা সম্পূর্ণ নিজস্ব ভাষায় নতুন করে লিখতে হবে।

২. মানুষের লেখার স্বাভাবিক ছন্দ ও বৈচিত্র্য (Human Burstiness & Flow):
   - কোনো কৃত্রিম বা রোবোটিক টেমপ্লেট ফলো করবে না।
   - বাক্যের দৈর্ঘ্যে বৈচিত্র্য আনবে: কিছু বাক্য হবে ছোট ও ক্ষুরধার (যেমন: 'ঘটনাস্থলেই প্রাণহানি ঘটে।' বা 'এতে এলাকায় তীব্র ক্ষোভের সৃষ্টি হয়।'), আবার কিছু বাক্য হবে তথ্যবহুল ও বিশদ। এটি AI ডিটেক্টরে মানবীয় স্কোর নিশ্চিত করে।
   - মাঠপর্যায়ের অভিজ্ঞ সাংবাদিকের মতো জীবন্ত ও গতিশীল ভাষায় ঘটনা উপস্থাপন করবে।

৩. সংবাদের গভীরতা অনুযায়ী কাঠামো বিন্যাস:
   - ফেসবুক ভাইরাল বা আলোচিত সংবাদ: কেন এটি সামাজিক মাধ্যমে তোলপাড় বা ক্ষোভের সৃষ্টি করেছে এবং নেটিজেনদের কী প্রতিক্রিয়া তা তুলে ধরবে।
   - বিস্তারিত সংবাদ (উন্নয়ন, অর্থনীতি, প্রকল্প, রাজনীতি, ফিচার): ৩-৫টি পরিচ্ছন্ন অনুচ্ছেদে রূপ দেবে। প্রয়োজন অনুযায়ী অর্থবহ সাব-হেডলাইন ব্যবহার করবে।
   - ব্রেকিং বা দুর্ঘটনা/অপরাধ: কোনো বাহুল্য ছাড়া দ্রুত ও ধারালো ২-৩ অনুচ্ছেদে মূল তথ্য তুলে ধরবে।
   - প্রতিটি অনুচ্ছেদ ২-৩ বাক্যের মধ্যে রাখবে এবং অনুচ্ছেদগুলোর মাঝে ডাবল ফাঁকা লাইন দেবে।

৪. কঠোরভাবে নিষিদ্ধ:
   - কোনো প্রকার ইমোজি বা আইকন (🚨, 👉, 🔹, 💬, 📰, 📌 ইত্যাদি) ব্যবহার করা যাবে না।
   - কোনো চটুল বা এআই-ক্লিশে বাক্য (যেমন: 'আসুন জেনে নেই', 'চলুন দেখে নেওয়া যাক', 'আমাদের সাথেই থাকুন', 'এটি অত্যন্ত গুরুত্বপূর্ণ একটি বিষয়', 'আলোচনার ঝড় উঠেছে') লেখা যাবে না।

সংবাদের মূল তথ্য:
- শিরোনাম: {title}
- মূল বিবরণ ও তথ্যসমূহ: {summary}
- এলাকা: {loc_display}
- ক্যাটাগরি: {'ফেসবুক ভাইরাল সংবাদ (সারা বাংলাদেশ)' if is_viral else 'আঞ্চলিক সংবাদ (উত্তরবঙ্গ)'}
- সূত্র: {source}

ফেসবুক ক্যাপশনের ফরম্যাট (fb_caption):
[হেডার: {'ভাইরাল সংবাদ | ' + loc_display if is_viral else 'ব্রেকিং নিউজ | ' + loc_display}]

[শিরোনাম ও প্রারম্ভিক উপস্থাপনা - সম্পূর্ণ মৌলিক ভাষায়]

[মূল বিবরণ - মৌলিক বাক্যগঠনে অনুচ্ছেদসমূহ, প্রতিটি প্যারার মাঝে ফাঁকা লাইন]

আপনার মতামত:
[পাঠকদের সুচিন্তিত মতামত জানতে ১টি দায়িত্বশীল ও প্রাসঙ্গিক প্রশ্ন]

তথ্যসূত্র: {source}

#NorthVoice #উত্তরবঙ্গ #{district} #{upazila if upazila else ''} #Viral #BangladeshNews

ফটোকার্ডের তথ্য (template ও headline_html):
- template: {'viral' if is_viral else "'breaking' (North Voice এর প্রধান সিগনেচার ক্রিমসন কার্ড) | 'quote' (বক্তব্য/উক্তি) | 'inqilab_style' (রাজনীতি/শাসনব্যবস্থা)"}
- headline_html: ফটোকার্ডের জন্য অত্যন্ত আকর্ষণীয় ও সংক্ষিপ্ত (২-৩ লাইন) হেডলাইন। মূল শব্দগুচ্ছকে <span class="highlight">শব্দ</span> দিয়ে মার্ক করবে।
- sub_headline: "{'সারা দেশ' if is_viral and not upazila else (upazila + ' বার্তা' if upazila else district + ' বার্তা')}"

নিচের JSON ফরম্যাটে সরাসরি উত্তর প্রদান করো (অন্য কোনো টেক্সট বা মার্কডাউন ছাড়া):
{{
  "is_relevant": true,
  "template": "viral" | "breaking" | "quote" | "inqilab_style",
  "headline_html": "হেডলাইন টেক্সট <span class='highlight'>হাইলাইট</span> সহ...",
  "sub_headline": "{'সারা দেশ' if is_viral and not upazila else (upazila if upazila else district) + ' বার্তা'}",
  "speaker_name": "বক্তার নাম (শুধুমাত্র quote টেমপ্লেটে)",
  "speaker_title": "বক্তার পদবি (শুধুমাত্র quote টেমপ্লেটে)",
  "fb_caption": "সম্পূর্ণ মৌলিক, মানবীয় ভাষায় রচিত ১০০% ইমোজিহীন ফেসবুক ক্যাপশন...",
  "district": "{district}"
}}
"""

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7  # High temperature ensures human-like burstiness, rich vocabulary, and eliminates AI patterns
                    )
                )
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()

                data = json.loads(raw_text)
                logger.info(f"AI Editor successfully drafted humanized news using template: '{data.get('template')}' for '{title[:30]}...'")
                return data
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt+1}/{max_retries} failed: {e}")
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))

        logger.error(f"All Gemini retries failed. Last error: {last_error}. Using fallback editor.")
        return self.fallback_analyze(title, summary, source, district, upazila)
