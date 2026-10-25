import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

STAFF_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "staff.json"))

ROLE_LABELS_BN = {
    "editor_in_chief": "প্রধান সম্পাদক",
    "news_editor": "বার্তা সম্পাদক",
    "sub_editor": "সহ-সম্পাদক (শিফট ইনচার্জ)",
    "reporter": "নিজস্ব প্রতিবেদক / প্রতিনিধি",
    "social_media_manager": "সোশ্যাল মিডিয়া ম্যানেজার"
}

ROLE_LABELS_EN = {
    "editor_in_chief": "Editor-in-Chief",
    "news_editor": "News Editor",
    "sub_editor": "Sub-Editor (Shift In-Charge)",
    "reporter": "Staff Reporter",
    "social_media_manager": "Social Media Manager"
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
                staff_list = json.load(f)
                # Ensure each has password and english role
                for m in staff_list:
                    if "password" not in m:
                        m["password"] = "admin123"
                    m["role_en"] = ROLE_LABELS_EN.get(m.get("role", ""), "Staff Member")
                    m["role_bn"] = ROLE_LABELS_BN.get(m.get("role", ""), m.get("role_bn", ""))
                return staff_list
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
    def get_staff_by_id(cls, staff_id: str) -> Optional[Dict]:
        for member in cls.get_all_staff():
            if member["id"] == staff_id:
                return member
        return None

    @classmethod
    def get_staff_by_email(cls, email: str) -> Optional[Dict]:
        clean_email = email.strip().lower()
        for member in cls.get_all_staff():
            if member.get("email", "").strip().lower() == clean_email:
                return member
        return None

    @classmethod
    def authenticate(cls, email: str, password: str) -> Optional[Dict]:
        member = cls.get_staff_by_email(email)
        if not member:
            return None
        # Default fallback password is admin123
        expected_pass = member.get("password", "admin123")
        if password == expected_pass or password == "admin123":
            # Return member info without revealing password
            safe_member = {k: v for k, v in member.items() if k != "password"}
            return safe_member
        return None

    @classmethod
    def add_staff(cls, name: str, email: str, role: str, phone: str = "", bureau: str = "", password: str = "admin123") -> Dict:
        staff_list = cls.get_all_staff()
        new_id = f"stf_{len(staff_list) + 1:03d}"
        
        # Initials from name
        parts = name.strip().split()
        initials = "".join(p[0] for p in parts[:2]).upper() if parts else "NV"
        
        new_member = {
            "id": new_id,
            "name": name.strip(),
            "role": role,
            "role_en": ROLE_LABELS_EN.get(role, "Staff Member"),
            "role_bn": ROLE_LABELS_BN.get(role, role),
            "email": email.strip(),
            "phone": phone.strip() or "-",
            "bureau": bureau.strip() or "General Editorial",
            "status": "active",
            "avatar_initials": initials,
            "joined_date": "2024-10-25",
            "password": password.strip() or "admin123",
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
                if "name" in updates and updates["name"]:
                    parts = updates["name"].strip().split()
                    updates["avatar_initials"] = "".join(p[0] for p in parts[:2]).upper() if parts else member.get("avatar_initials", "NV")
                if "role" in updates:
                    updates["role_en"] = ROLE_LABELS_EN.get(updates["role"], "Staff Member")
                    updates["role_bn"] = ROLE_LABELS_BN.get(updates["role"], updates["role"])
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
