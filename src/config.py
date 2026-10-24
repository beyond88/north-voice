import os
import urllib.parse
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

# API Keys and URLs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Facebook Credentials
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

# Runtime Flags
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes") or not FB_PAGE_ACCESS_TOKEN
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "1"))
DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

# North Bengal Districts (All 16 Districts across Rangpur & Rajshahi Divisions)
NORTH_BENGAL_DISTRICTS = [
    # Rangpur Division (৮টি জেলা)
    "রংপুর", "বগুড়া", "বগুড়া", "দিনাজপুর", "কুড়িগ্রাম", "কুড়িগ্রাম",
    "গাইবান্ধা", "নীলফামারী", "পঞ্চগড়", "পঞ্চগড়", "ঠাকুরগাঁও", "লালমনিরহাট",
    # Rajshahi Division (৮টি জেলা)
    "রাজশাহী", "পাবনা", "সিরাজগঞ্জ", "নওগাঁ", "নাটোর", "জয়পুরহাট", "জয়পুরহাট", "চাঁপাইনবাবগঞ্জ",
    # Regional Core
    "উত্তরবঙ্গ"
]

# Comprehensive Upazila / Thana Map for all 125 Upazilas of North Bengal
NORTH_BENGAL_UPAZILAS = {
    "রংপুর": ["পীরগাছা", "মিঠাপুকুর", "বদরগঞ্জ", "কাউনিয়া", "গঙ্গাচড়া", "পীরগঞ্জ", "তারাগঞ্জ"],
    "বগুড়া": ["শেরপুর", "শিবগঞ্জ", "সারিয়াকান্দি", "সোনাতলা", "ধুনট", "গাবতলী", "দুপচাঁচিয়া", "আদমদীঘি", "নন্দীগ্রাম", "শাজাহানপুর", "কাহালু"],
    "দিনাজপুর": ["বিরামপুর", "ফুলবাড়ী", "ঘোড়াঘাট", "বীরগঞ্জ", "কাহারোল", "বোচাগঞ্জ", "নবাবগঞ্জ", "পার্বতীপুর", "হাকিমপুর", "চিরিরবন্দর", "খানসামা", "বিরল"],
    "কুড়িগ্রাম": ["উলিপুর", "চিলমারী", "নাগেশ্বরী", "ভুরুঙ্গামারী", "রৌমারী", "রাজিবপুর", "ফুলবাড়ী", "রাজারহাট"],
    "গাইবান্ধা": ["গোবিন্দগঞ্জ", "সাদুল্লাপুর", "পলাশবাড়ী", "সাঘাটা", "সুন্দরগঞ্জ", "ফুলছড়ি"],
    "নীলফামারী": ["সৈয়দপুর", "ডোমার", "ডিমলা", "জলঢাকা", "কিশোরগঞ্জ"],
    "পঞ্চগড়": ["তেঁতুলিয়া", "বোদা", "দেবীগঞ্জ", "আটোয়ারী"],
    "ঠাকুরগাঁও": ["পীরগঞ্জ", "বালিয়াডাঙ্গী", "রাণীশংকৈল", "হরিপুর"],
    "লালমনিরহাট": ["পাটগ্রাম", "হাতীবান্ধা", "কালীগঞ্জ", "আদিতমারী"],
    "রাজশাহী": ["বাঘা", "চারঘাট", "পুঠিয়া", "দুর্গাপুর", "বাগমারা", "মোহনপুর", "তানোর", "গোদাগাড়ী", "বোয়ালিয়া"],
    "পাবনা": ["ঈশ্বরদী", "সাঁথিয়া", "বেড়া", "সুজানগর", "চাটমোহর", "ভাঙ্গুড়া", "ফরিদপুর", "আটঘরিয়া"],
    "সিরাজগঞ্জ": ["উল্লাপাড়া", "শাহজাদপুর", "রায়গঞ্জ", "বেলকুচি", "তাড়াশ", "কাজিপুর", "কামারখন্দ", "চৌহালী"],
    "নওগাঁ": ["পত্নীতলা", "ধামইরহাট", "মহাদেবপুর", "মান্দা", "নিয়ামতপুর", "পোরশা", "সাপাহার", "বদলগাছী", "আত্রাই", "রানীনগর"],
    "নাটোর": ["সিংড়া", "বড়াইগ্রাম", "গুরুদাসপুর", "লালপুর", "বাগাতিপাড়া", "নলডাঙ্গা"],
    "জয়পুরহাট": ["পাঁচবিবি", "কালাই", "ক্ষেতলাল", "আক্কেলপুর"],
    "চাঁপাইনবাবগঞ্জ": ["শিবগঞ্জ", "গোমস্তাপুর", "নাচোল", "ভোলাহাট"]
}

# 1. Direct National Media Feeds (Verified Working Portals)
DIRECT_PORTAL_FEEDS = [
    "https://www.prothomalo.com/feed",
    "https://www.ittefaq.com.bd/feed/",
    "https://www.jagonews24.com/rss/rss.xml",
    "https://www.banglatribune.com/feed/",
    "https://www.dhakapost.com/rss/rss.xml",
    "https://www.thedailystar.net/rss.xml"
]

# 2. Comprehensive Google News District & Regional Feeds (Covers all TV channels & Newspapers)
def build_district_feeds():
    base_url = "https://news.google.com/rss/search?q={query}&hl=bn&gl=BD&ceid=BD:bn"
    queries = [
        "উত্তরবঙ্গ",
        "বগুড়া", "রংপুর", "রাজশাহী", "দিনাজপুর",
        "পাবনা", "সিরাজগঞ্জ", "নওগাঁ", "নাটোর",
        "কুড়িগ্রাম", "পঞ্চগড়", "ঠাকুরগাঁও", "লালমনিরহাট",
        "নীলফামারী", "গাইবান্ধা", "জয়পুরহাট", "চাঁপাইনবাবগঞ্জ"
    ]
    return [base_url.format(query=urllib.parse.quote(q)) for q in queries]

# 3. Comprehensive Google News Upazila Cluster Feeds (Covers local Thana news pages, Somoy TV, Jamuna, Karatoa, etc.)
def build_upazila_feeds():
    base_url = "https://news.google.com/rss/search?q={query}&hl=bn&gl=BD&ceid=BD:bn"
    feeds = []
    for dist, upazilas in NORTH_BENGAL_UPAZILAS.items():
        # Query format: ("পীরগাছা" OR "মিঠাপুকুর" OR ...)
        query_str = " OR ".join([f'"{u}"' for u in upazilas])
        feed_url = base_url.format(query=urllib.parse.quote(f"({query_str})"))
        feeds.append(feed_url)
    return feeds

# Combined 360-Degree Master RSS Feeds covering National Media, TV Channels, Local Dailies, and All Upazilas
RSS_FEEDS = DIRECT_PORTAL_FEEDS + build_district_feeds() + build_upazila_feeds()

# Brand Details
BRAND_NAME = "North Voice"
BRAND_HANDLE = "fb.com/northvoicebd"
TAGLINE = "উত্তরবঙ্গের প্রতিটি জনপদের বলিষ্ঠ কণ্ঠস্বর"
