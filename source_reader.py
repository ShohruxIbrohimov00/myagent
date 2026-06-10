"""
Manba o'qigich (Telethon).

SIZNING Telegram akkauntingiz orqali manba kanallarga "quloq soladi".
Yangi post chiqishi bilan uni (matn + media) olib, berilgan callback ga uzatadi.

Qo'llab-quvvatlanadigan media: rasm, video, GIF, hujjat (PDF/kitob/fayl).
Video/GIF/fayldan AI ko'rishi uchun thumbnail (rasm) ham olinadi.

Eslatma: oddiy bot begona kanallarni o'qiy olmaydi — shuning uchun bu yerda
user-akkaunt (Telethon) ishlatiladi. Yopiq kanal bo'lsa, akkauntingiz a'zo
bo'lishi shart.
"""
from __future__ import annotations

import logging
import os
from typing import Awaitable, Callable

from telethon import TelegramClient, events

import config

log = logging.getLogger("reader")

# Callback turi: yangi post haqidagi ma'lumotni qabul qiladi
PostCallback = Callable[[dict], Awaitable[None]]


class SourceReader:
    def __init__(self, on_post: PostCallback):
        self._on_post = on_post
        self.client = TelegramClient(config.SESSION_PATH, config.API_ID, config.API_HASH)

    async def start(self) -> None:
        """Akkauntga ulanadi (birinchi marta telefon raqam + kod so'raydi)."""
        await self.client.start()
        me = await self.client.get_me()
        log.info("Telethon ulandi: %s", me.username or me.first_name)

        # MUHIM: bot akkaunti begona kanallarni o'qiy olmaydi!
        if getattr(me, "bot", False):
            log.error(
                "DIQQAT: Telethon BOT akkaunti bilan kirgan (@%s). "
                "Botlar begona kanal postlarini o'qiy OLMAYDI! "
                "'%s.session' faylini o'chirib, qayta ishga tushiring va telefon "
                "RAQAMingizni kiriting (bot token emas).",
                me.username, config.SESSION_PATH,
            )

        # Manba kanallarga kira olishimizni oldindan tekshiramiz
        for ch in config.SOURCE_CHANNELS:
            try:
                ent = await self.client.get_entity(ch)
                log.info("Kanal topildi: %s (id=%s)", ch, getattr(ent, "id", "?"))
            except Exception as e:
                log.error("Kanalga kira olmadim: %s -> %s "
                          "(akkauntingiz shu kanalga a'zomi?)", ch, e)

        @self.client.on(events.NewMessage(chats=config.SOURCE_CHANNELS))
        async def _handler(event):
            try:
                await self._handle(event)
            except Exception:
                log.exception("Postni o'qishda xato")

        log.info("Kuzatilayotgan kanallar: %s", ", ".join(config.SOURCE_CHANNELS))

    async def _handle(self, event) -> None:
        msg = event.message
        text = (msg.message or "").strip()

        # Albom (bir nechta media bitta postda): faqat izohli (matnli) bo'lagini
        # olamiz, qolgan media-only bo'laklarni o'tkazib yuboramiz (spam bo'lmasin).
        if getattr(msg, "grouped_id", None) and not text:
            return

        # Mediani aniqlab, yuklab olamiz.
        #   media_path  -> kanalga joylash uchun fayl
        #   media_type  -> "photo" | "video" | "animation" | "document" | None
        #   image_path  -> AI ko'rishi uchun rasm (rasmning o'zi yoki thumbnail)
        media_path = None
        media_type = None
        image_path = None
        media_name = None
        base = os.path.join(config.MEDIA_DIR, f"{event.chat_id}_{msg.id}")

        try:
            if msg.photo:
                media_path = await msg.download_media(file=base + ".jpg")
                media_type = "photo"
                image_path = media_path

            elif msg.gif:  # animatsiya (GIF / jonli rasm)
                media_path = await msg.download_media(file=base + ".mp4")
                media_type = "animation"
                image_path = await self._download_thumb(msg, base)

            elif msg.video or msg.video_note:
                media_path = await msg.download_media(file=base + ".mp4")
                media_type = "video"
                image_path = await self._download_thumb(msg, base)

            elif msg.document:  # PDF / kitob / arxiv / boshqa fayl
                # Asl fayl nomini saqlaymiz (kengaytma to'g'ri bo'lishi uchun)
                orig = getattr(msg.file, "name", None)
                fname = f"{base}_{orig}" if orig else base + (getattr(msg.file, "ext", "") or "")
                media_path = await msg.download_media(file=fname)
                media_type = "document"
                media_name = orig
                image_path = await self._download_thumb(msg, base)
        except Exception:
            log.exception("Mediani yuklab olishda xato (id=%s)", msg.id)

        # Bo'sh post (na matn, na media) — keraksiz
        if not text and not media_path:
            return

        chat = await event.get_chat()
        channel_name = getattr(chat, "username", None) or getattr(chat, "title", str(event.chat_id))

        log.info("📥 Yangi post: %s (id=%s, %d belgi, media=%s)",
                 channel_name, msg.id, len(text), media_type or "yo'q")

        await self._on_post({
            "channel": str(channel_name),
            "message_id": msg.id,
            "text": text,
            "media_path": media_path,
            "media_type": media_type,
            "media_name": media_name,
            "image_path": image_path,
        })

    async def _download_thumb(self, msg, base: str) -> str | None:
        """Video/GIF/fayl dan AI ko'rishi uchun eng katta thumbnail (rasm) ni oladi."""
        try:
            return await msg.download_media(file=base + "_thumb.jpg", thumb=-1)
        except Exception:
            return None

    async def run_until_disconnected(self) -> None:
        await self.client.run_until_disconnected()
