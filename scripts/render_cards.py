"""Re-render the sample cards from saved results (no Gemini, no Facebook, no DB) and print them as base64."""
import json, base64, sys
sys.path.insert(0, ".")
from src.news_hunter import NewsHunter, is_valid_image_url
from src.card_generator import CardGenerator
h, g = NewsHunter(), CardGenerator()
for i, line in enumerate(open("scripts/results.jsonl", encoding="utf-8")):
    d = json.loads(line)
    _, img, _ = h.resolve_article_meta(d["link"])
    print("IMG", i, img)
    payload = {"title": d["title"], "headline_html": d["headline_html"], "template": d["template"],
               "district": d["district"], "upazila": d["upazila"], "source": d["source"], "image_url": img,
               "sub_headline": f"{d['upazila']} বার্তা" if d.get("upazila") else f"{d['district']} বার্তা"}
    card = g.generate_card(payload)
    print("CARD", i, card)
    if card:
        b = base64.b64encode(open(card, "rb").read()).decode()
        for j in range(0, len(b), 4000):
            print(f"B64 {i} {b[j:j+4000]}")
