"""
AI processor — loyihaning "aqli".

Bitta manba postni oladi va:
1. Gemini bilan baholaydi: reklama/keraksizmi? -> shunday bo'lsa tashlaydi.
2. Arzisa, Shohrux tilida qayta yozadi (rasm bo'lsa uni ham ko'radi).
3. So'nggi postlar bilan solishtiradi: bir xil yangilik (takror) bo'lsa tashlaydi.

Natija: tayyor post dict yoki None (o'tkazib yuborildi).
"""
from __future__ import annotations

import json
import logging

import database as db
import persona
from gemini_client import client as gemini

log = logging.getLogger("processor")


def _read_image_part(path: str) -> dict | None:
    """Rasmni Gemini tushunadigan ko'rinishga keltiradi (qo'shimcha kutubxonasiz)."""
    try:
        with open(path, "rb") as f:
            return {"mime_type": "image/jpeg", "data": f.read()}
    except Exception:
        log.warning("Rasmni o'qib bo'lmadi: %s", path)
        return None


def _parse_json(raw: str) -> dict | None:
    """Gemini javobidan JSON ni ajratib oladi (```json ... ``` bo'lsa ham)."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # "json" so'zini olib tashlash
        if s[:4].lower() == "json":
            s = s[4:]
    # birinchi { dan oxirgi } gacha
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None


async def _is_duplicate(topic: str, text: str) -> bool:
    """Yaqinda chiqqan postlar bilan solishtirib, takrormi tekshiradi."""
    recent = await db.recent_topics(limit=25)
    if not recent:
        return False
    answer = await gemini.generate(
        [persona.dedup_prompt(topic, text, recent)], temperature=0.0
    )
    return answer.strip().upper().startswith("YES")


async def process(post: dict) -> dict | None:
    """
    post: {channel, message_id, text, image_path}
    return: tayyor post {topic, title, post, image_path, source} yoki None
    """
    text = post.get("text", "")
    image_path = post.get("image_path")
    media_type = post.get("media_type")

    # AI uchun media izohi
    if media_type == "photo":
        media_note = "Postga rasm biriktirilgan — uning mazmunini ham hisobga ol."
    elif media_type == "video":
        media_note = "Postga video biriktirilgan (uning bir lavhasi/tasviri berilgan)."
    elif media_type == "animation":
        media_note = "Postga GIF/animatsiya biriktirilgan."
    elif media_type == "document":
        media_note = ("Postga FAYL biriktirilgan (kitob/hujjat). Postda buni tabiiy "
                      "eslatib o'tishing mumkin (masalan: faylni quyida olishingiz mumkin).")
    else:
        media_note = "Postda media yo'q."

    # 1. Baholash + qayta yozish (rasm/thumbnail bo'lsa biriktiramiz)
    persona_text = await persona.get_persona()
    parts: list = [persona.filter_and_rewrite_prompt(persona_text, text, media_note)]
    if image_path:
        img = _read_image_part(image_path)
        if img:
            parts.append(img)

    raw = await gemini.generate(parts, temperature=0.8)
    data = _parse_json(raw)
    if not data:
        log.warning("JSON ajratib bo'lmadi, post o'tkazib yuborildi")
        return None

    if data.get("skip"):
        log.info("Tashlandi (%s): %s", post["channel"], data.get("reason", "—"))
        return None

    new_post = (data.get("post") or "").strip()
    topic = (data.get("topic") or "").strip()
    if not new_post:
        return None

    # 2. Dublikat tekshiruvi
    if await _is_duplicate(topic, new_post):
        log.info("Takror yangilik, tashlandi: %s", topic)
        return None

    return {
        "topic": topic,
        "title": (data.get("title") or "").strip(),
        "post": new_post,
        "image_path": image_path,
        "media_path": post.get("media_path"),
        "media_type": post.get("media_type"),
        "media_name": post.get("media_name"),
        "source": post["channel"],
    }
