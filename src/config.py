import os
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

# North Bengal Districts & Keywords for Filtering
NORTH_BENGAL_DISTRICTS = [
    # Rangpur Division
    "রংপুর", "বগুড়া", "বগুড়া", "দিনাজপুর", "কুড়িগ্রাম", "কুড়িগ্রাম",
    "গাইবান্ধা", "নীলফামারী", "পঞ্চগড়", "পঞ্চগড়", "ঠাকুরগাঁও", "লালমনিরহাট",
    # Rajshahi Division
    "রাজশাহী", "পাবনা", "সিরাজগঞ্জ", "নওগাঁ", "নাটোর", "জয়পুরহাট", "জয়পুরহাট", "চাঁপাইনবাবগঞ্জ"
]

# RSS Feeds of Major News Outlets
RSS_FEEDS = [
    # Google News RSS for North Bengal topics
    "https://news.google.com/rss/search?q=%E0%A6%89%E0%A6%A4%E0%A7%8D%E0%A6%A4%E0%A6%B0%E0%A6%AC%E0%A6%99%E0%A7%8D%E0%A6%97&hl=bn&gl=BD&ceid=BD:bn",
    "https://news.google.com/rss/search?q=%E0%A6%AC%E0%A6%97%E0%A7%81%E0%A7%9Call%E0%A6%B0%E0%A6%82%E0%A6%AA%E0%A7%81%E0%A6%B0&hl=bn&gl=BD&ceid=BD:bn",
    # Prothom Alo
    "https://www.prothomalo.com/feed",
    # Dhaka Post
    "https://www.dhakapost.com/rss",
    # Jago News 24
    "https://www.jagonews24.com/rss/rss.xml",
    # Bangla Tribune
    "https://www.banglatribune.com/feed",
    # Daily Star Bangla
    "https://bangla.thedailystar.net/rss",
    # BDNews24
    "https://bangla.bdnews24.com/rss.xml"
]

# Brand Details
BRAND_NAME = "North Voice"
BRAND_HANDLE = "fb.com/northvoicebd"
TAGLINE = "উত্তরবঙ্গের প্রতিটি জনপদের বলিষ্ঠ কণ্ঠস্বর"
