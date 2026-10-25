import os
import time
import base64
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, DRY_RUN, NORTH_BENGAL_DISTRICTS
from src.db import Database
from src.news_hunter import NewsHunter, is_valid_image_url
from src.ai_editor import AIEditor, clean_fb_caption, select_shuffled_template
from src.card_generator import CardGenerator, to_data_uri
from src.fb_poster import FacebookPoster
from src.spam_checker import PostSpamAuditor
from src.staff_manager import StaffManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NorthVoiceServer")

app = FastAPI(title="North Voice Editorial Newsroom Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Instances
db = Database()
hunter = NewsHunter()
editor = AIEditor()
generator = CardGenerator()
poster = FacebookPoster()

# Mount Static Admin Frontend
ADMIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin"))
app.mount("/assets", StaticFiles(directory=os.path.join(ADMIN_DIR, "assets")), name="assets")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(ADMIN_DIR, "index.html"))

@app.get("/{page}.html")
def read_page(page: str):
    file_path = os.path.join(ADMIN_DIR, f"{page}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Page not found")

# =========================================================================
# 1. Dashboard & Stats API
# =========================================================================
@app.get("/api/stats")
def get_dashboard_stats():
    mins_since_last = db.get_minutes_since_last_post()
    all_posts = db.get_all_posts(limit=200)
    
    # Calculate posts published today
    now = datetime.now(timezone.utc)
    today_posts = 0
    for p in all_posts:
        created_str = p.get("created_at")
        if created_str:
            try:
                dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if dt.date() == now.date():
                    today_posts += 1
            except Exception:
                pass

    staff_count = len(StaffManager.get_all_staff())
    last_tmpl = db.get_last_template()

    return {
        "total_posts": len(all_posts),
        "today_posts": today_posts,
        "staff_count": staff_count,
        "last_template": last_tmpl or "breaking",
        "minutes_since_last_post": round(mins_since_last, 1) if mins_since_last is not None else None,
        "safe_to_post": mins_since_last is None or mins_since_last >= 25.0,
        "page_status": "Active & Healthy",
        "fb_page_id": FB_PAGE_ID,
        "dry_run": DRY_RUN
    }

# =========================================================================
# 2. Published Posts Management & Deletion API
# =========================================================================
@app.get("/api/posts")
def get_posts(limit: int = 50):
    posts = db.get_all_posts(limit=limit)
    formatted = []
    for p in posts:
        fb_id_raw = p.get("fb_post_id", "")
        clean_fb_id = fb_id_raw.split("|tmpl:")[0].strip()
        tmpl = fb_id_raw.split("|tmpl:")[1].strip() if "|tmpl:" in fb_id_raw else "default"
        
        fb_url = f"https://facebook.com/{clean_fb_id}" if clean_fb_id and clean_fb_id not in ("dry_run", "mock") else None
        formatted.append({
            "id": p.get("id"),
            "url_hash": p.get("url_hash"),
            "headline": p.get("headline", ""),
            "news_url": p.get("news_url", ""),
            "fb_post_id": clean_fb_id,
            "fb_url": fb_url,
            "template": tmpl,
            "created_at": p.get("created_at", "")
        })
    return {"posts": formatted}

@app.delete("/api/posts/{url_hash}")
def delete_post(url_hash: str):
    # Fetch and delete from Supabase
    row_data = db.delete_post_by_hash(url_hash)
    fb_deleted = False
    
    if row_data and row_data.get("fb_post_id"):
        fb_pid = row_data["fb_post_id"]
        fb_deleted = poster.delete_post(fb_pid)
    
    return {
        "success": True,
        "message": "Post successfully deleted from database and Facebook page.",
        "fb_deleted": fb_deleted
    }

# =========================================================================
# 3. Live News Hunter & Scanner API
# =========================================================================
@app.get("/api/news/hunt")
def hunt_news(q: Optional[str] = None, district: Optional[str] = None, viral_only: bool = False):
    candidates = hunter.fetch_candidates()
    if not candidates:
        return {"candidates": []}

    # Filter by query if given
    if q:
        q_lower = q.strip().lower()
        candidates = [c for c in candidates if q_lower in c.get("title", "").lower() or q_lower in c.get("summary", "").lower()]

    # Filter by district if given
    if district and district != "সব জেলা":
        candidates = [c for c in candidates if c.get("district") == district or c.get("upazila") == district]

    # Filter by viral only
    if viral_only:
        candidates = [c for c in candidates if c.get("is_viral") or c.get("is_international")]

    # Sort by reach score
    candidates.sort(
        key=lambda x: (
            1 if (x.get("is_viral") or x.get("is_international")) else 0,
            x.get("reach_score", 0)
        ),
        reverse=True
    )

    # Return top 25 candidates
    results = []
    for c in candidates[:25]:
        results.append({
            "title": c.get("title", ""),
            "summary": c.get("summary", "")[:300] + "...",
            "link": c.get("link", ""),
            "district": c.get("district", "উত্তরবঙ্গ"),
            "upazila": c.get("upazila"),
            "source": c.get("source", "অনলাইন ডেস্ক"),
            "image_url": c.get("image_url"),
            "reach_score": c.get("reach_score", 0),
            "is_viral": c.get("is_viral", False),
            "is_international": c.get("is_international", False),
            "recommended_template": c.get("template", "breaking")
        })

    return {"candidates": results, "total": len(candidates)}

# =========================================================================
# 4. Instant Publish & Preview API
# =========================================================================
@app.post("/api/news/preview")
def preview_news_card(payload: Dict):
    template = payload.get("template", "breaking")
    temp_payload = {
        "title": payload.get("title", ""),
        "headline_html": payload.get("headline_html") or payload.get("title", ""),
        "sub_headline": payload.get("sub_headline", ""),
        "district": payload.get("district", "উত্তরবঙ্গ"),
        "upazila": payload.get("upazila"),
        "source": payload.get("source", "অনলাইন ডেস্ক"),
        "image_url": payload.get("image_url"),
        "template": template,
        "is_viral": payload.get("is_viral", False),
        "is_international": payload.get("is_international", False),
        "speaker_name": payload.get("speaker_name", ""),
        "speaker_title": payload.get("speaker_title", "")
    }

    card_path = generator.generate_card(temp_payload, output_dir="/tmp")
    if card_path and os.path.exists(card_path):
        uri = to_data_uri(card_path)
        try:
            os.remove(card_path)
        except Exception:
            pass
        return {"success": True, "image_uri": uri, "template": template}
    else:
        raise HTTPException(status_code=400, detail="Could not generate card preview. Valid authentic photo is required.")

@app.post("/api/news/publish")
def publish_news_now(payload: Dict):
    title = payload.get("title", "")
    link = payload.get("link", f"manual_{int(time.time())}")
    
    # 1. Resolve authentic photo
    img_url = payload.get("image_url")
    if not img_url or not is_valid_image_url(img_url):
        resolved_url, resolved_img = hunter.resolve_article_meta(link)
        if resolved_img:
            img_url = resolved_img
            payload["image_url"] = img_url

    if not img_url:
        raise HTTPException(status_code=400, detail="প্রকৃত সংবাদের ছবি ছাড়া ফটোকার্ড পোস্ট করা সম্ভব নয়। অনুগ্রহ করে একটি আসল ফটো দিন।")

    # 2. AI Editing & Template Dynamic Selection
    recent_headlines = db.get_recent_headlines(limit=30)
    last_tmpl = db.get_last_template()
    
    analysis = editor.analyze_news(payload, recent_headlines=recent_headlines, last_template=last_tmpl)
    if not analysis:
        raise HTTPException(status_code=400, detail="AI সম্পাদক সংবাদটি প্রস্তুত করতে ব্যর্থ হয়েছে।")

    news_payload = {**payload, **analysis}
    if "template" in payload and payload["template"]:
        news_payload["template"] = payload["template"]

    # 3. Generate Photocard
    card_path = generator.generate_card(news_payload)
    if not card_path or not os.path.exists(card_path):
        raise HTTPException(status_code=400, detail="ফটোকার্ড রেন্ডার করা সম্ভব হয়নি। ছবির রেজোলিউশন চেক করুন।")

    # 4. Pre-Post Spam Audit
    caption = clean_fb_caption(news_payload.get("fb_caption", title))
    spam_score, spam_issues, is_safe = PostSpamAuditor.audit_post(
        news_payload=news_payload,
        image_path=card_path,
        caption=caption,
        recent_headlines=recent_headlines
    )

    if not is_safe:
        raise HTTPException(status_code=400, detail=f"ফেসবুক স্প্যাম ফিল্টার অ্যালার্ট: {spam_issues}")

    # 5. Publish to Facebook
    fb_post_id = poster.post_photocard(card_path, caption)
    if fb_post_id:
        # First comment
        poster.post_comment(fb_post_id, "উত্তরবঙ্গের নির্ভরযোগ্য খবরের জন্য আমাদের পেজে Follow দিয়ে যুক্ত থাকুন: https://facebook.com/northvoicebd")
        
        # Save to DB
        template_used = news_payload.get("template", "breaking")
        headline = news_payload.get("headline_html", title)
        db.save_post(news_url=link, headline=headline, fb_post_id=fb_post_id, template=template_used)
        
        return {
            "success": True,
            "message": "সংবাদটি সফলভাবে ফেসবুকে প্রকাশিত হয়েছে!",
            "fb_post_id": fb_post_id,
            "template": template_used,
            "spam_score": spam_score
        }
    else:
        raise HTTPException(status_code=500, detail="ফেসবুক পেজে পোস্ট আপলোড ব্যর্থ হয়েছে। টোকেন বা পারমিশন চেক করুন।")

# =========================================================================
# 5. Newspaper Staff Management API
# =========================================================================
@app.get("/api/staff")
def get_staff_members():
    staff = StaffManager.get_all_staff()
    return {"staff": staff}

@app.post("/api/staff")
def create_staff_member(payload: Dict):
    name = payload.get("name")
    email = payload.get("email")
    role = payload.get("role")
    phone = payload.get("phone", "")
    bureau = payload.get("bureau", "")
    
    if not name or not email or not role:
        raise HTTPException(status_code=400, detail="Name, Email and Role are required.")
    
    member = StaffManager.add_staff(name=name, email=email, role=role, phone=phone, bureau=bureau)
    return {"success": True, "staff": member}

@app.put("/api/staff/{staff_id}")
def update_staff_member(staff_id: str, updates: Dict):
    updated = StaffManager.update_staff(staff_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    return {"success": True, "staff": updated}

@app.delete("/api/staff/{staff_id}")
def delete_staff_member(staff_id: str):
    success = StaffManager.delete_staff(staff_id)
    if not success:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    return {"success": True, "message": "Staff member removed successfully."}

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
