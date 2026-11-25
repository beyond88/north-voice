"""One-off dry run: build one post with the live pipeline, but never publish and never write to Supabase."""
import os, json, time, logging, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
from src.db import Database, is_duplicate_story
from src.news_hunter import NewsHunter, is_valid_image_url
from src.ai_editor import AIEditor, clean_fb_caption, copy_overlap_ratio
from src.card_generator import CardGenerator
from src.spam_checker import PostSpamAuditor

db, hunter, editor, gen = Database(), NewsHunter(), AIEditor(), CardGenerator()
cands = hunter.fetch_candidates()
cands.sort(key=lambda x: x.get("reach_score", 0), reverse=True)
from collections import Counter
print("DISTRICTS:", Counter(c["district"] for c in cands).most_common())
for c in cands[:10]:
    print("CAND", c["reach_score"], c["district"], c.get("upazila"), "|", c["title"][:80], "|", c["source"])
recent = db.get_recent_headlines(limit=50)
last_t = db.get_last_template()
os.makedirs("output", exist_ok=True)
done = 0
for item in cands:
    if done >= 2: break
    if db.is_already_posted(item["link"]): continue
    dup, why = is_duplicate_story(item["title"], item.get("summary", ""), recent)
    if dup: continue
    url, img, body = hunter.resolve_article_meta(item["link"])
    if url: item["link"] = url
    if img and is_valid_image_url(img): item["image_url"] = img
    if body and len(body) > len(item.get("summary", "")): item["summary"] = body
    if not item.get("image_url") or not is_valid_image_url(item["image_url"]): continue
    a = editor.analyze_news(item, recent_headlines=recent, last_template=last_t)
    if not a or not a.get("is_relevant", True):
        print("SKIP", item["title"][:60], a and a.get("reason")); continue
    p = {**item, **a}
    card = gen.generate_card(p)
    if not card: continue
    cap = clean_fb_caption(p["fb_caption"])
    score, issues, safe = PostSpamAuditor.audit_post(p, card, cap, recent)
    res = {"title": item["title"], "district": item["district"], "upazila": item.get("upazila"), "source": item["source"],
           "link": item["link"], "template": p.get("template"), "headline_html": p.get("headline_html"),
           "copy_overlap": copy_overlap_ratio(cap, f"{item['title']} {item['summary']}"),
           "spam_score": score, "issues": issues, "safe": safe, "card": card, "caption": cap,
           "source_excerpt": item["summary"][:1500]}
    with open(f"output/sample_{done}.json", "w", encoding="utf-8") as f: json.dump(res, f, ensure_ascii=False, indent=2)
    print("RESULT", json.dumps({k: v for k, v in res.items() if k != "source_excerpt"}, ensure_ascii=False))
    last_t = p.get("template"); done += 1
print("SAMPLES:", done)
