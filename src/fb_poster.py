import os
import time
import logging
from typing import Optional, Dict
import requests
from src.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, DRY_RUN

logger = logging.getLogger(__name__)

class FacebookPoster:
    def __init__(self):
        self.page_id = FB_PAGE_ID
        self.access_token = FB_PAGE_ACCESS_TOKEN
        self.dry_run = DRY_RUN or not self.access_token or not self.page_id

        if self.dry_run:
            logger.info("FacebookPoster initialized in DRY-RUN mode (No live posts will be published).")
        else:
            logger.info(f"FacebookPoster initialized for Page ID: {self.page_id}")

    def post_photocard(self, image_path: str, caption: str) -> Optional[str]:
        """
        Uploads photocard to the Facebook Page with caption.
        Returns the Facebook Post ID upon success.
        """
        if self.dry_run:
            mock_id = f"mock_post_{int(time.time())}"
            logger.info("================ [DRY-RUN POST PREVIEW] ================")
            logger.info(f"Image: {image_path}")
            logger.info(f"Caption:\n{caption}")
            logger.info(f"Mock Post ID: {mock_id}")
            logger.info("=========================================================")
            return mock_id

        url = f"https://graph.facebook.com/v20.0/{self.page_id}/photos"
        try:
            with open(image_path, "rb") as img_file:
                payload = {
                    "caption": caption,
                    "published": "true",
                    "access_token": self.access_token
                }
                files = {
                    "source": img_file
                }
                response = requests.post(url, data=payload, files=files, timeout=30)
                data = response.json()

                if response.status_code == 200 and "id" in data:
                    post_id = data.get("post_id", data.get("id"))
                    logger.info(f"Successfully published post to Facebook! Post ID: {post_id}")
                    return post_id
                else:
                    err_msg = data.get("error", {}).get("message", "")
                    if "pages_manage_posts" in err_msg or "(#200)" in err_msg:
                        logger.error("🚨 FACEBOOK PERMISSION ERROR: Your Facebook Token does not have 'pages_manage_posts' permission! Please generate a Page Access Token with 'pages_manage_posts' and 'pages_read_engagement'.")
                    logger.error(f"Facebook Graph API Error ({response.status_code}): {data}")
                    return None
        except Exception as e:
            logger.error(f"Failed to post to Facebook: {e}")
            return None
