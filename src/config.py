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

# North Bengal Districts & Regional Keywords (All 16 Districts)
NORTH_BENGAL_DISTRICTS = [
    # Rangpur Division (৮টি জেলা)
    "রংপুর", "বগুড়া", "বগুড়া", "দিনাজপুর", "কুড়িগ্রাম", "কুড়িগ্রাম",
    "গাইবান্ধা", "নীলফামারী", "পঞ্চগড়", "পঞ্চগড়", "ঠাকুরগাঁও", "লালমনিরহাট",
    # Rajshahi Division (৮টি জেলা)
    "রাজশাহী", "পাবনা", "সিরাজগঞ্জ", "নওগাঁ", "নাটোর", "জয়পুরহাট", "জয়পুরহাট", "চাঁপাইনবাবগঞ্জ",
    # Regional Core
    "উত্তরবঙ্গ"
]

# 1. Direct Verified Working Portals RSS Feeds
DIRECT_PORTAL_FEEDS = [
    "https://www.prothomalo.com/feed",
    "https://www.ittefaq.com.bd/feed/",
    "https://www.jagonews24.com/rss/rss.xml",
    "https://www.banglatribune.com/feed/",
    "https://uttarbangasambad.com/feed/",
    "https://www.thedailystar.net/rss.xml"
]

# 2. Comprehensive Google News Feeds covering ALL TV Channels & Newspapers for every district
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

# Combined Master RSS Feeds (Covers Somoy TV, Jamuna, Channel 24, Jugantor, Samakal, Kaler Kantho, Inqilab, etc.)
RSS_FEEDS = DIRECT_PORTAL_FEEDS + build_district_feeds()

# Brand Details
BRAND_NAME = "North Voice"
BRAND_HANDLE = "fb.com/northvoicebd"
TAGLINE = "উত্তরবঙ্গের প্রতিটি জনপদের বলিষ্ঠ কণ্ঠস্বর"
