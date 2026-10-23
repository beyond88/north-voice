import os
import glob
import logging
import sys
from src.config import MAX_POSTS_PER_RUN, DRY_RUN
from src.db import Database
from src.news_hunter import NewsHunter
from src.ai_editor import AIEditor
from src.card_generator import CardGenerator
from src.fb_poster import FacebookPoster

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

    # Step 1: Hunt for fresh North Bengal news
    candidates = hunter.fetch_candidates()
    if not candidates:
        logger.info("No North Bengal news found in current scan. Agent exiting.")
        return

    posted_count = 0
    failed_attempts = 0
    MAX_FAILED_ATTEMPTS = 2

    # Step 2: Iterate and process
    for item in candidates:
        if failed_attempts >= MAX_FAILED_ATTEMPTS:
            logger.error(f"Stopping run: Reached maximum failed posting attempts ({MAX_FAILED_ATTEMPTS}). Please check Facebook permissions.")
            break
        link = item["link"]
        title = item["title"]

        logger.info(f"Checking candidate: {title[:50]}...")

        # Deduplication check in Supabase
        if db.is_already_posted(link):
            logger.info(f"Skipping already posted news: {link}")
            continue

        # Step 3: AI Editing & Formatting (Gemini)
        logger.info("Passing news to Gemini AI Editor...")
        analysis = editor.analyze_news(item)

        if not analysis or not analysis.get("is_relevant", True):
            logger.info("AI Editor evaluated news as low priority or not relevant. Skipping.")
            continue

        # Merge AI analysis with item
        news_payload = {**item, **analysis}

        # Step 4: Generate Photocard
        logger.info(f"Generating photocard using template '{news_payload.get('template')}'...")
        card_image_path = generator.generate_card(news_payload)

        if not card_image_path or not os.path.exists(card_image_path):
            logger.error("Failed to generate photocard. Skipping to next.")
            continue

        # Step 5: Post to Facebook
        caption = news_payload.get("fb_caption", f"{title}\n\n#NorthVoice #উত্তরবঙ্গ")
        logger.info("Publishing to Facebook...")
        fb_post_id = poster.post_photocard(card_image_path, caption)

        if fb_post_id:
            # Step 6: Save signature to Supabase
            headline = news_payload.get("headline_html", title)
            db.save_post(news_url=link, headline=headline, fb_post_id=fb_post_id)
            posted_count += 1
            logger.info(f"✅ Successfully processed and posted news ({posted_count}/{MAX_POSTS_PER_RUN})!")

            if posted_count >= MAX_POSTS_PER_RUN:
                logger.info(f"Reached MAX_POSTS_PER_RUN limit ({MAX_POSTS_PER_RUN}). Finishing current run.")
                break
        else:
            failed_attempts += 1
            logger.warning(f"Facebook posting failed ({failed_attempts}/{MAX_FAILED_ATTEMPTS}).")

    # Clean up temporary downloaded images
    for temp_file in glob.glob("output/temp_news_*"):
        try:
            os.remove(temp_file)
        except Exception:
            pass

    logger.info("==================================================")
    logger.info(f"   North Voice Agent finished. Posts published: {posted_count}")
    logger.info("==================================================")

if __name__ == "__main__":
    run_agent()
