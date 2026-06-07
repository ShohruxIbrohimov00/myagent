"""
Manba o'qigich (Telethon).

SIZNING Telegram akkauntingiz orqali manba kanallarga "quloq soladi".
Yangi post chiqishi bilan uni (matn + rasm) olib, berilgan callback ga uzatadi.

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

        # Faqat rasm/matnli postlarni olamiz (video/fayllarni hozircha o'tkazib yuboramiz)
        image_path = None
        if msg.photo:
            fname = os.path.join(config.MEDIA_DIR, f"{event.chat_id}_{msg.id}.jpg")
            image_path = await msg.download_media(file=fname)

        # Bo'sh post (na matn, na rasm) — keraksiz
        if not text and not image_path:
            return

        chat = await event.get_chat()
        channel_name = getattr(chat, "username", None) or getattr(chat, "title", str(event.chat_id))

        await self._on_post({
            "channel": str(channel_name),
            "message_id": msg.id,
            "text": text,
            "image_path": image_path,
        })

    async def run_until_disconnected(self) -> None:
        await self.client.run_until_disconnected()
