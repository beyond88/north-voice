import os
import glob
import time
import logging
import sys
from src.config import MAX_POSTS_PER_RUN, DRY_RUN
from src.db import Database, is_duplicate_story
from src.news_hunter import NewsHunter, is_valid_image_url
from src.ai_editor import AIEditor, clean_fb_caption
from src.card_generator import CardGenerator
from src.fb_poster import FacebookPoster
from src.spam_checker import PostSpamAuditor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NorthVoiceAgent")

def run_agent():
    logger.info("==================================================")
    logger.info("   🚀 North Voice Autonomous News Agent Started    ")
    logger.info("==================================================")

    db = Database()
    hunter = NewsHunter()
    editor = AIEditor()
    generator = CardGenerator()
    poster = FacebookPoster()

    # Step 0: Safe Posting Interval Audit (Anti-Spam Cooldown)
    # Meta / Facebook algorithms flag accounts posting < 25 mins apart as automated spam/bots.
    mins_since_last = db.get_minutes_since_last_post()
    if mins_since_last is not None and mins_since_last < 25.0:
        logger.info(f"⏳ Safe Posting Interval Cooldown: Last post published {mins_since_last:.1f} mins ago (< 25 min). Skipping to protect page health against Facebook spam flags.")
        return

    # Step 1: Hunt for fresh North Bengal news across all National & Upazila feeds
    candidates = hunter.fetch_candidates()
    if not candidates:
        logger.info("No North Bengal news found in current scan. Agent exiting.")
        return

    # Step 2: Sort all candidates in memory
    # Viral & International news take precedence over regular regional news
    # When both overlap in a cycle, viral content is ranked #1 and regular content is skipped.
    candidates.sort(
        key=lambda x: (
            1 if (x.get("is_viral") or x.get("is_international")) else 0,
            x.get("reach_score", 0)
        ),
        reverse=True
    )

    logger.info(f"Top 5 Ranked Candidates by Virality & Organic Reach Potential:")
    for idx, c in enumerate(candidates[:5], 1):
        loc = f"{c.get('upazila') or c.get('district')}"
        v_tag = " [VIRAL/INTL]" if (c.get("is_viral") or c.get("is_international")) else ""
        logger.info(f"  #{idx}{v_tag} [Reach Score: {c.get('reach_score', 0):.1f}] ({loc}) {c.get('title')[:60]}")

    posted_count = 0
    failed_attempts = 0
    MAX_FAILED_ATTEMPTS = 2

    # Fetch recent published headlines to detect evolving storylines & prevent duplicate stages
    recent_headlines = db.get_recent_headlines(limit=50)
    if recent_headlines:
        logger.info(f"Loaded {len(recent_headlines)} recent published headlines for multi-stage storyline tracking.")

    # Fetch last used photocard template for dynamic shuffling across all 5 designs
    last_template = db.get_last_template()
    if last_template:
        logger.info(f"Previous published photocard template: '{last_template}'. Shuffling enabled across 5 templates.")

    # Step 3: Process the highest ranked candidates (deduplicate on-demand)
    for item in candidates:
        if posted_count >= MAX_POSTS_PER_RUN:
            break
        if failed_attempts >= MAX_FAILED_ATTEMPTS:
            logger.error(f"Stopping run: Reached maximum failed posting attempts ({MAX_FAILED_ATTEMPTS}). Please check Facebook permissions.")
            break

        link = item["link"]
        title = item["title"]

        # Step 3.1: Fast URL deduplication check
        if db.is_already_posted(link):
            logger.debug(f"Skipping already posted news: {link}")
            continue

        # Step 3.2: Multi-stage Headline & Semantic Topic Deduplication (Python-level, 100% deterministic)
        is_dup, dup_reason = is_duplicate_story(title, item.get("summary", ""), recent_headlines)
        if is_dup:
            logger.info(f"Skipping candidate '{title[:40]}...': {dup_reason}")
            continue

        upazila = item.get("upazila")
        district = item.get("district", "উত্তরবঙ্গ")
        loc_display = f"{upazila}, {district}" if upazila else district

        logger.info(f"Processing candidate [Score: {item.get('reach_score', 0):.1f}]: {title[:50]} ({loc_display})...")

        # Step 4.1: Resolve real destination URL & verify authentic news photo FIRST
        resolved_url, resolved_img = hunter.resolve_article_meta(link)
        if resolved_url and resolved_url != link:
            if db.is_already_posted(resolved_url):
                logger.debug(f"Skipping resolved duplicate URL: {resolved_url}")
                continue
            item["link"] = resolved_url

        if resolved_img and is_valid_image_url(resolved_img):
            item["image_url"] = resolved_img

        img_url = item.get("image_url")
        if not img_url or not is_valid_image_url(img_url):
            logger.warning(f"No authentic news image found for '{title[:40]}'. Skipping to maintain premium visual standard.")
            continue

        # Pre-download and verify image authenticity before spending Gemini API quota
        temp_img_path = f"/tmp/check_{int(time.time()*1000)}.jpg"
        if not generator.download_image(img_url, temp_img_path):
            logger.warning(f"Failed to download image from {img_url[:60]}. Skipping candidate.")
            continue

        if generator.is_stock_or_white_graphic(temp_img_path):
            logger.warning(f"Image is stock illustration, white graphic, or search engine logo. Skipping candidate '{title[:40]}'.")
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)
            continue

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

        # Step 4.2: AI Editing & Formatting (Gemini 2.0/1.5 Flash with multi-stage storyline intelligence & 5-template shuffling)
        logger.info("Passing verified news to Gemini AI Editor with storyline tracking & template rotation...")
        analysis = editor.analyze_news(item, recent_headlines=recent_headlines, last_template=last_template)

        if not analysis or not analysis.get("is_relevant", True):
            reason = analysis.get("reason", "low priority") if analysis else "skipped"
            logger.info(f"AI Editor rejected candidate ({reason}). Skipping to next candidate.")
            continue

        # Merge AI analysis with item
        news_payload = {**item, **analysis}

        # Step 4.3: Generate Photocard with real photo
        template_used = news_payload.get("template", "breaking")
        logger.info(f"Generating photocard using template '{template_used}' (Rotated from previous: '{last_template}')...")
        card_image_path = generator.generate_card(news_payload)

        if not card_image_path or not os.path.exists(card_image_path):
            logger.warning(f"Photocard generation skipped for '{title[:40]}'. Trying next candidate with authentic photo...")
            continue

        # Step 4.4: Pre-Posting Facebook Spam Score Audit
        caption = news_payload.get("fb_caption", f"{title}\n\n#NorthVoice #উত্তরবঙ্গ")
        caption = clean_fb_caption(caption)

        spam_score, spam_issues, is_safe = PostSpamAuditor.audit_post(
            news_payload=news_payload,
            image_path=card_image_path,
            caption=caption,
            recent_headlines=recent_headlines
        )

        if not is_safe:
            logger.warning(f"🚨 Pre-Post Spam Audit REJECTED post [Spam Score: {spam_score}/100]. Issues: {spam_issues}. Skipping to prevent Facebook spam penalty.")
            continue

        logger.info(f"🛡️ Facebook Pre-Post Spam Audit PASSED [Spam Score: {spam_score}/100 - Clean & Safe]")

        # Step 4.5: Post to Facebook Page Feed
        logger.info("Publishing to Facebook...")
        fb_post_id = poster.post_photocard(card_image_path, caption)

        if fb_post_id:
            # Step 4.6: Post official first comment on the post
            first_comment = "উত্তরবঙ্গের প্রতিটি জনপদের নির্ভরযোগ্য খবরের জন্য আমাদের পেজে Follow দিয়ে যুক্ত থাকুন: https://facebook.com/northvoicebd"
            poster.post_comment(fb_post_id, first_comment)

            # Step 4.7: Save signatures to Supabase with template metadata
            headline = news_payload.get("headline_html", title)
            db.save_post(news_url=item["link"], headline=headline, fb_post_id=fb_post_id, template=template_used)
            if link != item["link"]:
                db.save_post(news_url=link, headline=headline, fb_post_id=fb_post_id, template=template_used)
            last_template = template_used
            posted_count += 1
            logger.info(f"✅ Successfully processed and posted news ({posted_count}/{MAX_POSTS_PER_RUN}) [Template: {template_used}]!")
        else:
            failed_attempts += 1
            logger.warning(f"Failed attempt {failed_attempts}/{MAX_FAILED_ATTEMPTS} to post news.")

    logger.info("==================================================")
    logger.info(f"   North Voice Agent finished. Posts published: {posted_count}")
    logger.info("==================================================")

if __name__ == "__main__":
    run_agent()
