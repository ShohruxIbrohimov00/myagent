"""
Admin bot (aiogram) + tasdiqlash oqimi.

Faqat ADMIN (siz) bilan ishlaydi. AI tayyorlagan postni preview qilib,
"✅ Tashlash / ✏️ Tahrir / ❌ Yo'q" tugmalari bilan ko'rsatadi.
Tasdiqlasangiz — TARGET_CHANNEL ga chiqaradi.
"""
from __future__ import annotations

import logging
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, FSInputFile, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

import config
import database as db
import persona
from gemini_client import client as gemini

log = logging.getLogger("bot")

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

CAPTION_LIMIT = 1024  # Telegram rasm/video izohining maksimal uzunligi
BOT_MAX_BYTES = 49 * 1024 * 1024  # Bot orqali yuborish limiti (~50MB); kattasi Telethon orqali

# Katta fayllarni (video/kitob) kanalga joylash uchun Telethon mijozi.
# main.py ishga tushganda set_telethon() orqali ulanadi.
_tele = None


def set_telethon(client) -> None:
    """main.py dan Telethon mijozini ulaydi (katta fayllarni yuborish uchun)."""
    global _tele
    _tele = client


class Form(StatesGroup):
    """Admin panel holatlari."""
    editing_persona = State()


def _is_admin(uid: int) -> bool:
    return uid == config.ADMIN_ID


def _approval_kb(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tashlash", callback_data=f"ok:{pid}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"no:{pid}"),
    ]])


def _panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Shaxsiyat", callback_data="menu:persona")],
        [InlineKeyboardButton(text="📊 Holat", callback_data="menu:status")],
    ])


def _persona_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ O'zgartirish", callback_data="persona:edit")],
        [InlineKeyboardButton(text="♻️ Standartga qaytarish", callback_data="persona:reset")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:home")],
    ])


# ---------------- Admin buyruqlari / panel ----------------
@router.message(Command("start"))
@router.message(Command("panel"))
async def cmd_start(msg: Message):
    if not _is_admin(msg.from_user.id):
        return  # begonalarga javob yo'q
    await msg.answer(
        "Salom! Men <b>Shohrux</b> 🤖\n\n"
        "Ochiq kanallarni kuzatib boraman, qiziqarli postlarni o'z uslubimda "
        "qayta yozaman va sizga tasdiq uchun yuboraman.\n\n"
        "Quyidagi paneldan boshqaring:",
        reply_markup=_panel_kb(),
    )


@router.message(Command("status"))
async def cmd_status(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    await msg.answer(_status_text())


def _status_text() -> str:
    return (
        "📊 <b>Holat</b>\n"
        f"{gemini.status()}\n"
        f"Manba kanallar: {len(config.SOURCE_CHANNELS)} ta\n"
        f"Maqsad kanal: {config.TARGET_CHANNEL}"
    )


# ---------------- Admin panel tugmalari ----------------
@router.callback_query(F.data == "menu:home")
async def menu_home(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    await cq.message.answer("🏠 Asosiy panel:", reply_markup=_panel_kb())
    await cq.answer()


@router.callback_query(F.data == "menu:status")
async def menu_status(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    await cq.message.answer(_status_text())
    await cq.answer()


@router.callback_query(F.data == "menu:persona")
async def menu_persona(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    text = await persona.get_persona()
    # Telegram xabar uzunligi cheklangani uchun kesib ko'rsatamiz
    shown = text if len(text) <= 3500 else text[:3500] + "\n…"
    await cq.message.answer(
        "👤 <b>Joriy shaxsiyat (Shohrux):</b>\n\n"
        f"<i>{shown}</i>\n\n"
        "O'zgartirish uchun tugmani bosing.",
        reply_markup=_persona_kb(),
    )
    await cq.answer()


@router.callback_query(F.data == "persona:edit")
async def persona_edit(cq: CallbackQuery, state: FSMContext):
    if not _is_admin(cq.from_user.id):
        return
    await state.set_state(Form.editing_persona)
    await cq.message.answer(
        "✏️ Yangi shaxsiyat matnini yuboring.\n\n"
        "Shohruxning kasbi, mahorati, fe'l-atvori, qadriyatlari va yozish uslubini "
        "to'liq yozib bering. Keyingi yuborgan xabaringiz shaxsiyat sifatida saqlanadi.\n\n"
        "Bekor qilish: /bekor"
    )
    await cq.answer()


@router.callback_query(F.data == "persona:reset")
async def persona_reset(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    await persona.reset_persona()
    await cq.message.answer("♻️ Shaxsiyat standart holatga qaytarildi.")
    await cq.answer("Bajarildi")


@router.message(Command("bekor"))
async def cancel_edit(msg: Message, state: FSMContext):
    if not _is_admin(msg.from_user.id):
        return
    if await state.get_state() is not None:
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=_panel_kb())


@router.message(Form.editing_persona)
async def save_persona(msg: Message, state: FSMContext):
    if not _is_admin(msg.from_user.id):
        return
    new_text = (msg.text or "").strip()
    if len(new_text) < 30:
        await msg.answer("Matn juda qisqa. Iltimos, to'liqroq shaxsiyat yozing (yoki /bekor).")
        return
    await persona.set_persona(new_text)
    await state.clear()
    await msg.answer("✅ Yangi shaxsiyat saqlandi! Endi postlar shu uslubda yoziladi.",
                     reply_markup=_panel_kb())


# ---------------- Tasdiqlash tugmalari ----------------
@router.callback_query(F.data.startswith("ok:"))
async def on_approve(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    pid = int(cq.data.split(":")[1])
    item = await db.get_pending(pid)
    if not item:
        await cq.answer("Bu post topilmadi (eskirgan).", show_alert=True)
        return

    try:
        await publish(item["post_text"], item.get("media_path"), item.get("media_type"))
        await db.add_published(item.get("topic") or "", item.get("title") or "")
        await db.del_pending(pid)
        await cq.message.edit_reply_markup(reply_markup=None)
        await cq.message.answer("✅ Kanalga joylandi.")
        await cq.answer("Joylandi!")
    except Exception as e:
        log.exception("Joylashda xato")
        await cq.answer(f"Xato: {e}", show_alert=True)


@router.callback_query(F.data.startswith("no:"))
async def on_reject(cq: CallbackQuery):
    if not _is_admin(cq.from_user.id):
        return
    pid = int(cq.data.split(":")[1])
    await db.del_pending(pid)
    await cq.message.edit_reply_markup(reply_markup=None)
    await cq.message.answer("❌ Tashlandi.")
    await cq.answer()


# ---------------- Yordamchi funksiyalar ----------------
def _file_size(path: str | None) -> int:
    try:
        return os.path.getsize(path) if path else 0
    except OSError:
        return 0


async def _send_media_bot(chat_id, media_path: str, media_type: str | None,
                          caption: str | None = None, reply_markup=None):
    """Media turiga qarab BOT orqali yuboradi (rasm/video/gif/fayl, <=50MB)."""
    f = FSInputFile(media_path)
    if media_type == "video":
        return await bot.send_video(chat_id, f, caption=caption, reply_markup=reply_markup)
    if media_type == "animation":
        return await bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)
    if media_type == "document":
        return await bot.send_document(chat_id, f, caption=caption, reply_markup=reply_markup)
    return await bot.send_photo(chat_id, f, caption=caption, reply_markup=reply_markup)


async def _send_media_telethon(chat_id, media_path: str, caption: str | None):
    """Katta fayllarni Telethon (user akkaunt) orqali yuboradi — 2GB gacha."""
    if _tele is None:
        raise RuntimeError("Katta fayl uchun Telethon ulanmagan")
    await _tele.send_file(chat_id, media_path, caption=caption or "", parse_mode="html")


async def publish(text: str, media_path: str | None, media_type: str | None) -> None:
    """Tayyor postni maqsad kanalga chiqaradi (media bo'lsa u bilan birga)."""
    target = config.TARGET_CHANNEL
    if not media_path:
        await bot.send_message(target, text)
        return

    big = _file_size(media_path) > BOT_MAX_BYTES
    caption = text if len(text) <= CAPTION_LIMIT else None

    if big and _tele is not None:
        # Katta fayl -> Telethon orqali
        await _send_media_telethon(target, media_path, caption)
    else:
        if caption is not None:
            await _send_media_bot(target, media_path, media_type, caption=caption)
        else:
            await _send_media_bot(target, media_path, media_type)

    # Matn uzun bo'lib caption sig'masa, qolganini alohida yuboramiz
    if caption is None:
        await bot.send_message(target, text)


async def send_for_approval(post: dict) -> None:
    """AI tayyorlagan postni adminga tasdiq uchun yuboradi."""
    pid = await db.add_pending({
        "topic": post.get("topic"),
        "title": post.get("title"),
        "post_text": post["post"],
        "media_path": post.get("media_path"),
        "media_type": post.get("media_type"),
        "source": post.get("source"),
    })

    preview = post["post"]
    media_path = post.get("media_path")
    media_type = post.get("media_type")
    kb = _approval_kb(pid)

    # Bot orqali ko'rsata olamizmi? (kichik fayl bo'lsa)
    can_preview = media_path and _file_size(media_path) <= BOT_MAX_BYTES

    try:
        if can_preview and len(preview) <= CAPTION_LIMIT:
            await _send_media_bot(config.ADMIN_ID, media_path, media_type,
                                  caption=preview, reply_markup=kb)
        else:
            if can_preview:
                await _send_media_bot(config.ADMIN_ID, media_path, media_type)
            elif media_path:
                # Katta fayl — preview'da ko'rsatmaymiz, faqat eslatamiz
                preview += "\n\n📎 <i>(Katta media biriktirilgan — tasdiqlasangiz kanalga chiqadi)</i>"
            await bot.send_message(config.ADMIN_ID, preview, reply_markup=kb)
    except Exception:
        log.exception("Adminga yuborishda xato")


async def notify_admin(text: str) -> None:
    """Adminga oddiy xabar (xato, ogohlantirish va h.k.)."""
    try:
        await bot.send_message(config.ADMIN_ID, text)
    except Exception:
        log.exception("notify_admin xato")
