import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

STAFF_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "staff.json"))

ROLE_LABELS = {
    "editor_in_chief": "প্রধান সম্পাদক",
    "news_editor": "বার্তা সম্পাদক",
    "sub_editor": "সহ-সম্পাদক (শিফট ইনচার্জ)",
    "reporter": "নিজস্ব প্রতিবেদক / প্রতিনিধি",
    "social_media_manager": "সোশ্যাল মিডিয়া ম্যানেজার"
}

ROLE_PERMISSIONS = {
    "editor_in_chief": ["all", "manage_staff", "publish_instant", "delete_posts", "edit_prompts", "system_settings"],
    "news_editor": ["publish_instant", "delete_posts", "edit_news", "scan_feeds", "view_analytics"],
    "sub_editor": ["scan_feeds", "draft_posts", "edit_news", "preview_cards"],
    "reporter": ["submit_news", "upload_photos", "draft_posts"],
    "social_media_manager": ["view_analytics", "monitor_spam", "view_posts"]
}

class StaffManager:
    @staticmethod
    def get_all_staff() -> List[Dict]:
        if not os.path.exists(STAFF_FILE):
            return []
        try:
            with open(STAFF_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read staff file: {e}")
            return []

    @staticmethod
    def save_all_staff(staff_list: List[Dict]) -> bool:
        try:
            os.makedirs(os.path.dirname(STAFF_FILE), exist_ok=True)
            with open(STAFF_FILE, "w", encoding="utf-8") as f:
                json.dump(staff_list, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save staff file: {e}")
            return False

    @classmethod
    def add_staff(cls, name: str, email: str, role: str, phone: str = "", bureau: str = "") -> Dict:
        staff_list = cls.get_all_staff()
        new_id = f"stf_{len(staff_list) + 1:03d}"
        
        # Initials from name
        parts = name.strip().split()
        initials = "".join(p[0] for p in parts[:2]) if parts else "ST"
        
        new_member = {
            "id": new_id,
            "name": name.strip(),
            "role": role,
            "role_bn": ROLE_LABELS.get(role, role),
            "email": email.strip(),
            "phone": phone.strip() or "-",
            "bureau": bureau.strip() or "সাধারণ বিভাগ",
            "status": "active",
            "avatar_initials": initials,
            "joined_date": "২০২৪-১০-২৫",
            "permissions": ROLE_PERMISSIONS.get(role, ["view_posts"])
        }
        staff_list.append(new_member)
        cls.save_all_staff(staff_list)
        return new_member

    @classmethod
    def update_staff(cls, staff_id: str, updates: Dict) -> Optional[Dict]:
        staff_list = cls.get_all_staff()
        for idx, member in enumerate(staff_list):
            if member["id"] == staff_id:
                if "role" in updates:
                    updates["role_bn"] = ROLE_LABELS.get(updates["role"], updates["role"])
                    updates["permissions"] = ROLE_PERMISSIONS.get(updates["role"], member.get("permissions", []))
                staff_list[idx] = {**member, **updates}
                cls.save_all_staff(staff_list)
                return staff_list[idx]
        return None

    @classmethod
    def delete_staff(cls, staff_id: str) -> bool:
        staff_list = cls.get_all_staff()
        filtered = [m for m in staff_list if m["id"] != staff_id]
        if len(filtered) < len(staff_list):
            cls.save_all_staff(filtered)
            return True
        return False
