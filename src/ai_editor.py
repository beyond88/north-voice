import json
import time
import logging
from typing import Dict, Optional
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, BRAND_NAME, BRAND_HANDLE

logger = logging.getLogger(__name__)

def clean_fb_caption(caption: str) -> str:
    """
    Removes any artificial category headers like 'ভাইরাল সংবাদ | সারা দেশ' 
    or 'ব্রেকিং নিউজ | সিংড়া, নাটোর' from the start of fb_caption.
    Ensures the Facebook post starts directly with the headline or story lead.
    """
    if not caption:
        return ""
    lines = caption.strip().splitlines()
    if lines:
        first_line = lines[0].strip()
        header_keywords = [
            "ভাইরাল সংবাদ", "ব্রেকিং নিউজ", "রাজনীতি ও সমসাময়িক", 
            "উত্তরবঙ্গ সমাচার", "বিশেষ বক্তব্য", "সারা দেশ", "ব্রেকিং"
        ]
        if any(kw in first_line for kw in header_keywords) and ("|" in first_line or ":" in first_line or "—" in first_line):
            lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
            return "\n".join(lines).strip()
    return caption.strip()

def select_shuffled_template(preferred: str, last_template: Optional[str], news_item: Dict) -> str:
    """
    Guarantees that consecutive posts NEVER use the same photocard template.
    Rotates dynamically across all 5 designs: viral, breaking, inqilab_style, quote, general
    based on the nature of the news content.
    """
    valid_templates = ["viral", "breaking", "inqilab_style", "quote", "general"]
    if preferred not in valid_templates:
        preferred = "breaking"

    if not last_template or preferred != last_template:
        return preferred

    # Preferred matches last_template: Rotate intelligently to the best secondary template
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")
    full_text = f"{title} {summary}".lower()
    is_viral = news_item.get("is_viral", False)
    is_intl = news_item.get("is_international", False) or news_item.get("district") == "আন্তর্জাতিক"

    if preferred == "viral":
        # Viral alternative:
        if any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন", "খুন", "বিক্ষোভ"]):
            return "breaking"
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি", "উক্তি", "ঘোষণা"]):
            return "quote"
        elif any(w in full_text for w in ["রাজনীতি", "সরকার", "কূটনীতি", "সীমান্ত", "নির্বাচন"]):
            return "inqilab_style"
        else:
            return "general"

    elif preferred == "breaking":
        # Breaking alternative:
        if is_viral or is_intl or any(w in full_text for w in ["ভাইরাল", "তোলপাড়", "তোলপাড়", "আলোড়ন", "সামাজিক"]):
            return "viral"
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি", "ঘোষণা"]):
            return "quote"
        elif any(w in full_text for w in ["রাজনীতি", "সরকার", "সীমান্ত", "প্রশাসন"]):
            return "inqilab_style"
        else:
            return "general"

    elif preferred == "inqilab_style":
        # Inqilab alternative:
        if any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি", "উক্তি"]):
            return "quote"
        elif is_viral or is_intl:
            return "viral"
        elif any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "বিক্ষোভ"]):
            return "breaking"
        else:
            return "general"

    elif preferred == "quote":
        # Quote alternative:
        if any(w in full_text for w in ["রাজনীতি", "সরকার", "সীমান্ত", "প্রশাসন"]):
            return "inqilab_style"
        elif is_viral or is_intl:
            return "viral"
        elif any(w in full_text for w in ["নিহত", "আহত", "গ্রেপ্তার", "জরুরি"]):
            return "breaking"
        else:
            return "general"

    elif preferred == "general":
        # General alternative:
        if is_viral or is_intl:
            return "viral"
        elif any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার"]):
            return "breaking"
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি"]):
            return "quote"
        else:
            return "inqilab_style"

    # Strict failsafe: pick any valid template different from last_template
    for candidate_tmpl in valid_templates:
        if candidate_tmpl != last_template:
            return candidate_tmpl

    return "breaking"

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

    def fallback_analyze(self, title: str, summary: str, source: str, district: str, upazila: Optional[str] = None, is_viral: bool = False, is_international: bool = False, recent_headlines: Optional[list] = None, last_template: Optional[str] = None) -> Dict:
        """Intelligently routes news across all 5 templates with dynamic shuffling in clean journalistic style."""
        # Enforce multi-stage deduplication even in fallback editor
        if recent_headlines:
            from src.db import is_duplicate_story
            is_dup, dup_reason = is_duplicate_story(title, summary, recent_headlines)
            if is_dup:
                logger.info(f"Fallback Editor rejected candidate: {dup_reason}")
                return {
                    "is_relevant": False,
                    "reason": dup_reason
                }

        full_text = f"{title} {summary}"
        loc_display = f"{upazila}, {district}" if upazila else district

        # 1. International News (Yellow Badge + Dark Slate Card - Global)
        if district == "আন্তর্জাতিক" or is_international:
            preferred_template = "viral"
            subhead = "আন্তর্জাতিক"
            cta_question = "আন্তর্জাতিক এই ঘটনাটিকে আপনি কীভাবে দেখছেন? আপনার মতামত কমেন্টে জানান।"
            hashtags = "#NorthVoice #আন্তর্জাতিক #InternationalNews #Viral"
        # 2. Facebook Viral Topics (Yellow Badge + Dark Slate Card - Whole Bangladesh)
        elif is_viral or any(vt in full_text.lower() for vt in ["ভাইরাল", "তোলপাড়", "তোলপাড়", "আলোড়ন", "সামাজিক যোগাযোগমাধ্যম", "নেটিজেনদের", "ভিডিও ছড়িয়ে"]):
            preferred_template = "viral"
            subhead = "সারা দেশ"
            cta_question = "সামাজিক যোগাযোগমাধ্যমে তোলপাড় সৃষ্টি করা এই ঘটনাটিকে আপনি কীভাবে দেখছেন? আপনার সুচিন্তিত মতামত কমেন্টে জানান।"
            upazila_tag = f"#{upazila} " if upazila else ""
            hashtags = f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#Viral #BangladeshNews"
        # 3. Quote Card (Dark Editorial)
        elif any(w in full_text for w in ["বলেন", "মন্তব্য", "দাবি করেন", "হুশিয়ারি", "উক্তি", "ঘোষণা"]):
            preferred_template = "quote"
            subhead = f"{upazila} বার্তা" if upazila else (f"{district} বার্তা" if district != "সারা দেশ" else "সারা দেশ")
            cta_question = f"বক্তার এই বক্তব্যের সাথে আপনি কি একমত? আপনার যুক্তিযুক্ত মতামত কমেন্টে তুলে ধরুন।"
            upazila_tag = f"#{upazila} " if upazila else ""
            hashtags = f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#NorthBengal #BangladeshNews"
        # 4. Inqilab Style (Politics, bilateral, governance)
        elif any(w in full_text for w in ["রাজনীতি", "সীমান্ত", "তিস্তা", "নির্বাচন", "বিএনপি", "জামায়াত", "সরকার", "আন্দোলন"]):
            preferred_template = "inqilab_style"
            subhead = f"{upazila} বার্তা" if upazila else (f"{district} বার্তা" if district != "সারা দেশ" else "সারা দেশ")
            cta_question = f"এই সমসাময়িক প্রেক্ষাপট নিয়ে আপনার মূল্যায়ন কী? কমেন্টে আলোচনা করুন।"
            upazila_tag = f"#{upazila} " if upazila else ""
            hashtags = f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#NorthBengal #BangladeshNews"
        # 5. General / Broadsheet News (Agriculture, Development, Economy, Education, Environment)
        elif any(w in full_text for w in ["উন্নয়ন", "কৃষি", "ফসল", "শিক্ষা", "অর্থনীতি", "প্রকল্প", "আবহাওয়া", "শীত", "বৃষ্টি", "নদী"]):
            preferred_template = "general"
            subhead = f"{upazila} বার্তা" if upazila else (f"{district} বার্তা" if district != "সারা দেশ" else "সারা দেশ")
            cta_question = f"উত্তরবঙ্গের সামগ্রিক উন্নয়নে এ ধরনের উদ্যোগ কতটা তাৎপর্যপূর্ণ বলে আপনি মনে করেন? আপনার মতামত জানান।"
            upazila_tag = f"#{upazila} " if upazila else ""
            hashtags = f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#NorthBengal #BangladeshNews"
        # 6. Signature Crimson Photocard (Breaking, Accidents, Crime, Alerts)
        else:
            preferred_template = "breaking"
            subhead = f"{upazila} বার্তা" if upazila else (f"{district} বার্তা" if district != "সারা দেশ" else "সারা দেশ")
            if any(w in full_text for w in ["নিহত", "আহত", "দুর্ঘটনা", "গ্রেপ্তার", "আটক", "আগুন", "ডাকাতি", "খুন", "অবরোধ"]):
                cta_question = f"এ বিষয়ে আপনার এলাকার সার্বিক পরিস্থিতি সম্পর্কে আপনার মতামত কমেন্টে জানান।"
            else:
                cta_question = f"এ বিষয়ে আপনার সুচিন্তিত মতামত কমেন্টে জানান।"
            upazila_tag = f"#{upazila} " if upazila else ""
            hashtags = f"#NorthVoice #উত্তরবঙ্গ #{district} {upazila_tag}#NorthBengal #BangladeshNews"

        item_ctx = {
            "title": title,
            "summary": summary,
            "district": district,
            "is_viral": is_viral,
            "is_international": is_international
        }
        final_template = select_shuffled_template(preferred_template, last_template, item_ctx)

        formatted_body = self.format_clean_story(summary, max_chars=900)
        if not formatted_body:
            formatted_body = title

        caption = (
            f"{title}\n\n"
            f"{formatted_body}\n\n"
            f"আপনার মতামত:\n"
            f"{cta_question}\n\n"
            f"তথ্যসূত্র: {source}\n\n"
            f"{hashtags}"
        )

        return {
            "is_relevant": True,
            "template": final_template,
            "headline_html": title,
            "sub_headline": subhead,
            "speaker_name": "",
            "speaker_title": "",
            "fb_caption": caption,
            "district": district,
            "upazila": upazila
        }

    def analyze_news(self, news_item: Dict, recent_headlines: Optional[list] = None, last_template: Optional[str] = None) -> Optional[Dict]:
        """
        Uses Gemini 2.0/1.5 Flash to analyze news, intelligently decide between deep long-form
        journalism vs crisp breaking reports, pick from 5 visual templates with dynamic shuffling,
        track multi-stage evolving storylines, and write 100% human-grade, zero-plagiarism broadsheet copy.
        """
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        source = news_item.get("source", "গণমাধ্যম")
        district = news_item.get("district", "উত্তরবঙ্গ")
        upazila = news_item.get("upazila")
        is_viral = news_item.get("is_viral", False)
        is_international = news_item.get("is_international", False) or district == "আন্তর্জাতিক"
        loc_display = "আন্তর্জাতিক" if is_international else (f"{upazila}, {district}" if upazila else district)

        if not self.client:
            return self.fallback_analyze(title, summary, source, district, upazila, is_viral=is_viral, is_international=is_international, recent_headlines=recent_headlines, last_template=last_template)

        if is_international:
            category_text = "আন্তর্জাতিক সংবাদ (বিদেশের ঘটনা)"
            default_subhead = "আন্তর্জাতিক"
            hashtags_template = "#NorthVoice #আন্তর্জাতিক #InternationalNews #Viral"
        elif is_viral:
            category_text = "ফেসবুক ভাইরাল সংবাদ (সারা বাংলাদেশ)"
            default_subhead = "সারা দেশ"
            hashtags_template = f"#NorthVoice #উত্তরবঙ্গ #{district} #{upazila if upazila else ''} #Viral #BangladeshNews"
        else:
            category_text = "আঞ্চলিক সংবাদ (উত্তরবঙ্গ)"
            default_subhead = f"{upazila} বার্তা" if upazila else f"{district} বার্তা"
            hashtags_template = f"#NorthVoice #উত্তরবঙ্গ #{district} #{upazila if upazila else ''} #BangladeshNews"

        recent_headlines_block = ""
        if recent_headlines:
            cleaned_recent = [h.strip() for h in recent_headlines[:15] if h.strip()]
            if cleaned_recent:
                recent_headlines_block = "\n".join([f"- {h}" for h in cleaned_recent])

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
   - আন্তর্জাতিক সংবাদ: ঘটনাটি কোন দেশের এবং সামাজিক মাধ্যমে কেন ছড়িয়ে পড়েছে তা তুলে ধরবে।
   - বিস্তারিত সংবাদ (উন্নয়ন, অর্থনীতি, প্রকল্প, রাজনীতি, ফিচার): ৩-৫টি পরিচ্ছন্ন অনুচ্ছেদে রূপ দেবে। প্রয়োজন অনুযায়ী অর্থবহ সাব-হেডলাইন ব্যবহার করবে।
   - ব্রেকিং বা দুর্ঘটনা/অপরাধ: কোনো বাহুল্য ছাড়া দ্রুত ও ধারালো ২-৩ অনুচ্ছেদে মূল তথ্য তুলে ধরবে।
   - প্রতিটি অনুচ্ছেদ ২-৩ বাক্যের মধ্যে রাখবে এবং অনুচ্ছেদগুলোর মাঝে ডাবল ফাঁকা লাইন দেবে।

৪. কঠোরভাবে নিষিদ্ধ ও ক্যাটাগরি বিধি:
   - কোনো প্রকার ইমোজি বা আইকন (🚨, 👉, 🔹, 💬, 📰, 📌 ইত্যাদি) ব্যবহার করা যাবে না।
   - কোনো চটুল বা এআই-ক্লিশে বাক্য (যেমন: 'আসুন জেনে নেই', 'চলুন দেখে নেওয়া যাক', 'আমাদের সাথেই থাকুন', 'আলোচনার ঝড় উঠেছে') লেখা যাবে না।
   - ক্যাপশনের শুরুতে কোনো প্রকার হেডার বা ক্যাটাগরি লাইন (যেমন: 'ভাইরাল সংবাদ | সারা দেশ', 'ব্রেকিং নিউজ | সিংড়া, নাটোর', 'আন্তর্জাতিক' ইত্যাদি) লেখা সম্পূর্ণ নিষিদ্ধ। পোস্ট সরাসরি মূল সংবাদের আকর্ষণীয় শিরোনাম বা প্রারম্ভিক উপস্থাপনা দিয়ে শুরু হবে।
   - অত্যন্ত গুরুত্বপূর্ণ (সাব-হেডলাইন ও ফটোকার্ড ব্যাজ): যদি ঘটনাটি বিদেশের/আন্তর্জাতিক হয় (যেমন: চীন, ভারত, মধ্যপ্রাচ্য, ইউরোপ, যুক্তরাষ্ট্র ইত্যাদি), তবে sub_headline এবং ফটোকার্ডের গোল্ডেন পিল ব্যাজ অবশ্যই 'আন্তর্জাতিক' হতে হবে। কখনোই 'সারা দেশ' লেখা যাবে না!

৫. কঠোরভাবে এক ঘটনায় একবারই পোস্ট নীতি (Strict One-Post-Per-Topic Anti-Spam Policy):
আমাদের পেজে সম্প্রতি প্রকাশিত সংবাদের শিরোনামসমূহ:
{recent_headlines_block if recent_headlines_block else "(পূর্বে কোনো পোস্ট সংরক্ষিত নেই)"}

যদি বর্তমান সংবাদটি উপরের পূর্বে প্রকাশিত কোনো সংবাদের ঘটনার বিষয়ের সাথে সম্পর্কিত হয় (হোক তা একই ঘটনার খবর বা সেই ঘটনার পরবর্তী স্টেজ/তদন্ত/মামলা/গ্রেপ্তার):
-> ফেসবুকের স্প্যাম পলিসি সুরক্ষায় এক ঘটনায় দ্বিতীয় পর্ব বা পুনরাবৃত্তি প্রকাশ সম্পূর্ণ নিষেধ! কোনো ফলো-আপ বা নেক্সট স্টেজ পোস্ট করা যাবে না।
-> সাথে সাথে "is_relevant": false এবং "reason": "এক বিষয়ে একবারই পোস্ট নীতি (ফেসবুক স্প্যাম ফিল্টার প্রতিরোধ)" প্রদান করবে।

৬. ফটোকার্ডের ৫টি ডিজাইন টেমপ্লেট ও নির্বাচন নির্দেশিকা (Template Dynamic Shuffling):
আমাদের মোট ৫টি ফটোকার্ড ডিজাইন টেমপ্লেট রয়েছে:
- 'viral': ডার্ক স্লেট ব্লু ও সোনালী পিল ব্যাজ (সামাজিক যোগাযোগ মাধ্যমে তোলপাড়, ক্ষোভ, ট্রোল, ভাইরাল ভিডিও বা আন্তর্জাতিক চমকপ্রদ ঘটনা)।
- 'breaking': North Voice সিগনেচার ক্রিমসন/লাল ব্যাকগ্রাউন্ড ও লাইভ ব্যাজ (দুর্ঘটনা, অপরাধ, তাৎক্ষণিক ব্রেকিং, বিক্ষোভ, অগ্নিকাণ্ড বা জরুরি আঞ্চলিক ঘটনা)।
- 'inqilab_style': ক্ল্যাসিক ব্রডশিট সম্পাদকীয় কার্ড (রাজনীতি, কূটনীতি, প্রশাসন, নির্বাচন, তিস্তা, সীমান্ত ও শাসনব্যবস্থা)।
- 'quote': ডার্ক সম্পাদকীয় উক্তি কার্ড (উদ্ধৃতি চিহ্ন সহ কোনো শীর্ষ ব্যক্তির আলোচিত বক্তব্য, উক্তি, ঘোষণা বা হুঁশিয়ারি)।
- 'general': আধুনিক এলিগ্যান্ট ডার্ক ব্লু ফ্রেমড ফটোকার্ড (জনস্বার্থ, উন্নয়ন, অর্থনীতি, কৃষি, শিক্ষা, পরিবেশ বা সাধারণ সংবাদ)।

সর্বশেষ প্রকাশিত পোস্টে ব্যবহৃত ফটোকার্ডের ডিজাইন ছিল: '{last_template or "কোনোটি নয়"}'
কঠোর শর্ত: আমাদের পেজে পরপর দুই পোস্টে কখনোই একই ফটোকার্ড ডিজাইন টেমপ্লেট ব্যবহার করা যাবে না! সংবাদের বিষয়বস্তুর সাথে সবচেয়ে মানানসই এমন একটি টেমপ্লেট বেছে নাও যা পূর্ববর্তী ব্যবহৃত '{last_template or "কোনোটি নয়"}' থেকে সম্পূর্ণ ভিন্ন।

সংবাদের মূল তথ্য:
- শিরোনাম: {title}
- মূল বিবরণ ও তথ্যসমূহ: {summary}
- এলাকা: {loc_display}
- ক্যাটাগরি: {category_text}
- সূত্র: {source}

ফেসবুক ক্যাপশনের ফরম্যাট (fb_caption):
[সংবাদের শিরোনাম বা আকর্ষণীয় প্রারম্ভিক উপস্থাপনা - সম্পূর্ণ মৌলিক ভাষায় (কোনো হেডার বা ক্যাটাগরি লাইন ছাড়া)]

[মূল বিবরণ - মৌলিক বাক্যগঠনে অনুচ্ছেদসমূহ, প্রতিটি প্যারার মাঝে ফাঁকা লাইন]

আপনার মতামত:
[পাঠকদের সুচিন্তিত মতামত জানতে ১টি দায়িত্বশীল ও প্রাসঙ্গিক প্রশ্ন]

তথ্যসূত্র: {source}

{hashtags_template}

ফটোকার্ডের তথ্য (template ও headline_html):
- template: "viral" | "breaking" | "inqilab_style" | "quote" | "general" (পূর্ববর্তী '{last_template or "কোনোটি নয়"}' থেকে ভিন্ন)
- headline_html: ফটোকার্ডের জন্য অত্যন্ত আকর্ষণীয় ও সংক্ষিপ্ত (২-৩ লাইন) হেডলাইন। মূল শব্দগুচ্ছকে <span class="highlight">শব্দ</span> দিয়ে মার্ক করবে।
- sub_headline: "{default_subhead}"

নিচের JSON ফরম্যাটে সরাসরি উত্তর প্রদান করো (অন্য কোনো টেক্সট বা মার্কডাউন ছাড়া):
{{
  "is_relevant": true,
  "reason": "কারণ (যদি is_relevant false হয়)",
  "template": "viral" | "breaking" | "inqilab_style" | "quote" | "general",
  "headline_html": "হেডলাইন টেক্সট <span class='highlight'>হাইলাইট</span> সহ...",
  "sub_headline": "{default_subhead}",
  "speaker_name": "বক্তার নাম (শুধুমাত্র quote টেমপ্লেটে)",
  "speaker_title": "বক্তার পদবি (শুধুমাত্র quote টেমপ্লেটে)",
  "fb_caption": "সম্পূর্ণ মৌলিক, মানবীয় ভাষায় রচিত ১০০% ইমোজিহীন ফেসবুক ক্যাপশন...",
  "district": "{district}"
}}
"""

        # Dynamic model selection with automatic discovery & robust fallbacks
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-2.5-pro",
            "gemini-3.8-flash",
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7
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
                if "fb_caption" in data and data["fb_caption"]:
                    data["fb_caption"] = clean_fb_caption(data["fb_caption"])

                # Enforce strict non-repetition: consecutive posts must never use the same template
                chosen_tmpl = data.get("template", "breaking")
                final_tmpl = select_shuffled_template(chosen_tmpl, last_template, news_item)
                data["template"] = final_tmpl

                logger.info(f"AI Editor ({model_name}) successfully drafted news using template: '{final_tmpl}' (Preferred: {chosen_tmpl}, Last: {last_template}) for '{title[:30]}...'")
                return data
            except Exception as e:
                logger.warning(f"Gemini API ({model_name}) failed: {e}")
                last_error = e
                time.sleep(1)

        logger.error(f"All Gemini models failed. Last error: {last_error}. Using fallback editor.")
        return self.fallback_analyze(title, summary, source, district, upazila, is_viral=is_viral, is_international=is_international, recent_headlines=recent_headlines, last_template=last_template)
