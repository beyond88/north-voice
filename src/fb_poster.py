import os
import json
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
        Uploads photocard to the Facebook Page and publishes directly to the Page Timeline Feed / List view.
        Uses the official Meta 2-step process:
          Step 1: Upload photo as unpublished media asset (published=false) to /{page_id}/photos
          Step 2: Create feed post with attached_media on /{page_id}/feed
        This ensures the post is placed on the Page's main timeline feed and List view (not just Photos tab).
        """
        if self.dry_run:
            mock_id = f"mock_post_{int(time.time())}"
            logger.info("================ [DRY-RUN POST PREVIEW] ================")
            logger.info(f"Image: {image_path}")
            logger.info(f"Caption:\n{caption}")
            logger.info(f"Mock Post ID: {mock_id}")
            logger.info("=========================================================")
            return mock_id

        # Step 1: Upload photo as unpublished media asset
        upload_url = f"https://graph.facebook.com/v20.0/{self.page_id}/photos"
        try:
            with open(image_path, "rb") as img_file:
                upload_payload = {
                    "published": "false",
                    "access_token": self.access_token
                }
                files = {
                    "source": img_file
                }
                upload_res = requests.post(upload_url, data=upload_payload, files=files, timeout=30)
                upload_data = upload_res.json()

                if upload_res.status_code != 200 or "id" not in upload_data:
                    err_msg = upload_data.get("error", {}).get("message", "")
                    err_code = upload_data.get("error", {}).get("code")
                    if "Session has expired" in err_msg or err_code == 190:
                        logger.error("🚨 FACEBOOK TOKEN EXPIRED: Your FB_PAGE_ACCESS_TOKEN has expired! Please generate a Permanent Page Access Token (Expires: Never).")
                    elif "pages_manage_posts" in err_msg or "(#200)" in err_msg:
                        logger.error("🚨 FACEBOOK PERMISSION ERROR: Your Facebook Token does not have 'pages_manage_posts' permission!")
                    logger.error(f"Failed to upload photo asset ({upload_res.status_code}): {upload_data}")
                    return None

                media_fbid = upload_data["id"]
                logger.info(f"Photo asset uploaded successfully (Media ID: {media_fbid})")

                # Step 2: Publish directly to /{page-id}/feed with attached_media
                # This guarantees the post appears on the Page's main timeline / list view / news feed!
                feed_url = f"https://graph.facebook.com/v20.0/{self.page_id}/feed"
                feed_payload = {
                    "message": caption,
                    "attached_media[0]": json.dumps({"media_fbid": str(media_fbid)}),
                    "access_token": self.access_token
                }
                feed_res = requests.post(feed_url, data=feed_payload, timeout=30)
                feed_data = feed_res.json()

                if feed_res.status_code == 200 and "id" in feed_data:
                    post_id = feed_data["id"]
                    logger.info(f"✅ Successfully published to Page Feed/List View! Post ID: {post_id}")
                    return post_id
                else:
                    logger.error(f"Feed post error ({feed_res.status_code}): {feed_data}. Falling back to media asset ID.")
                    return media_fbid
        except Exception as e:
            logger.error(f"Failed to post to Facebook: {e}")
            return None

    def post_comment(self, post_id: str, message: str) -> bool:
        """
        Posts an official first comment under the published post.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN COMMENT] Post ID {post_id}: {message}")
            return True

        url = f"https://graph.facebook.com/v20.0/{post_id}/comments"
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        try:
            res = requests.post(url, data=payload, timeout=20)
            data = res.json()
            if res.status_code == 200 and "id" in data:
                logger.info(f"✅ Successfully posted first comment on post {post_id} (Comment ID: {data.get('id')})")
                return True
            else:
                logger.warning(f"Could not post first comment on post {post_id}: {data}")
                return False
        except Exception as e:
            logger.warning(f"Failed to post first comment on post {post_id}: {e}")
            return False

    def delete_post(self, post_id: str) -> bool:
        """
        Deletes a published post from the Facebook Page Feed via Graph API.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN DELETE] Post ID: {post_id}")
            return True

        if not post_id or post_id in ("dry_run", "mock"):
            return True

        clean_post_id = post_id.split("|tmpl:")[0].strip()
        url = f"https://graph.facebook.com/v20.0/{clean_post_id}"
        params = {"access_token": self.access_token}
        try:
            res = requests.delete(url, params=params, timeout=20)
            data = res.json()
            if res.status_code == 200 and data.get("success", False):
                logger.info(f"✅ Successfully deleted post {clean_post_id} from Facebook Page Feed.")
                return True
            else:
                logger.warning(f"Could not delete post {clean_post_id} from Facebook: {data}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete post {clean_post_id} from Facebook: {e}")
            return False

    def update_post_caption(self, post_id: str, new_caption: str) -> bool:
        """
        Updates an existing published post's caption/message on Facebook Page Feed.
        This modifies the existing old post in-place without creating a duplicate.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN UPDATE] Post ID {post_id} -> New Caption: {new_caption[:40]}...")
            return True

        if not post_id or post_id in ("dry_run", "mock"):
            return True

        clean_post_id = post_id.split("|tmpl:")[0].strip()
        url = f"https://graph.facebook.com/v20.0/{clean_post_id}"
        payload = {
            "message": new_caption,
            "access_token": self.access_token
        }
        try:
            res = requests.post(url, data=payload, timeout=20)
            data = res.json()
            if res.status_code == 200 and data.get("success", False):
                logger.info(f"✅ Successfully updated post {clean_post_id} on Facebook Page Feed.")
                return True
            else:
                logger.warning(f"Could not update post {clean_post_id} on Facebook: {data}")
                return False
        except Exception as e:
            logger.error(f"Failed to update post {clean_post_id} on Facebook: {e}")
            return False
