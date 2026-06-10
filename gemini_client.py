"""
Gemini mijozi + API kalit rotatsiyasi.

Mantiq: bir nechta API kalit bo'ladi. Birining kunlik limiti tugasa
(429 / quota xatosi), avtomatik keyingi kalitga o'tadi. Tugagan kalitlar
keyingi kun (UTC yarim tunda) qayta tiklanadi.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import google.generativeai as genai
from google.api_core import exceptions as gexc

import config

log = logging.getLogger("gemini")


class GeminiClient:
    def __init__(self, api_keys: list[str], model_name: str):
        if not api_keys:
            raise ValueError("Kamida bitta API kalit kerak")
        self._keys = api_keys
        self._model_name = model_name
        self._idx = 0  # hozirgi kalit indeksi
        # Har bir kalit qaysi sanada "tugagan" deb belgilangani (UTC kuni)
        self._exhausted_on: dict[int, str] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _is_available(self, idx: int) -> bool:
        """Kalit bugun ishlatish uchun ochiqmi (tugamaganmi)?"""
        return self._exhausted_on.get(idx) != self._today()

    def _mark_exhausted(self, idx: int) -> None:
        self._exhausted_on[idx] = self._today()
        log.warning("Kalit #%d limiti tugadi, keyingisiga o'tamiz", idx + 1)

    def _next_available(self, start: int) -> int | None:
        """start dan keyin ishlaydigan birinchi kalit indeksini topadi."""
        for step in range(len(self._keys)):
            idx = (start + step) % len(self._keys)
            if self._is_available(idx):
                return idx
        return None  # hammasi tugagan

    def status(self) -> str:
        """Admin uchun qisqa holat: nechta kalit faol."""
        active = sum(1 for i in range(len(self._keys)) if self._is_available(i))
        return f"Gemini kalitlar: {active}/{len(self._keys)} faol (hozirgi #{self._idx + 1})"

    async def generate(self, parts: list, *, temperature: float = 0.8) -> str:
        """
        Matn (va ixtiyoriy rasm) yuborib, javob matnini qaytaradi.
        parts: matn (str) va/yoki rasm (PIL.Image yoki dict) ro'yxati.
        Limit tugasa avtomatik kalit almashtiradi.
        """
        async with self._lock:
            tried = 0
            while tried < len(self._keys):
                idx = self._next_available(self._idx)
                if idx is None:
                    raise RuntimeError(
                        "Barcha Gemini kalitlari limiti tugagan. Ertaga qayta urinib ko'ring "
                        "yoki yangi kalit qo'shing."
                    )
                self._idx = idx
                try:
                    return await self._call(idx, parts, temperature)
                except (gexc.ResourceExhausted, gexc.TooManyRequests):
                    # Bu kalit limitga yetdi -> tugagan deb belgilab keyingisiga o'tamiz
                    self._mark_exhausted(idx)
                    self._idx = (idx + 1) % len(self._keys)
                    tried += 1
                except (gexc.ServiceUnavailable, gexc.DeadlineExceeded) as e:
                    # Vaqtinchalik xato -> biroz kutib qayta urinamiz (kalitni tugagan demaymiz)
                    log.warning("Vaqtinchalik xato (%s), 3s kutamiz", type(e).__name__)
                    await asyncio.sleep(3)
                    tried += 1
            raise RuntimeError("Gemini javob bermadi (barcha urinishlar tugadi).")

    async def _call(self, idx: int, parts: list, temperature: float) -> str:
        """Bitta kalit bilan haqiqiy chaqiruv (alohida thread'da, bloklamaslik uchun)."""
        def _sync() -> str:
            genai.configure(api_key=self._keys[idx])
            
            # Model nomini o'zgaruvchidan to'g'ridan-to'g'ri olamiz
            model = genai.GenerativeModel(self._model_name)
            
            resp = model.generate_content(
                parts,
                generation_config={"temperature": temperature},
            )
            return (resp.text or "").strip()

        return await asyncio.to_thread(_sync)


# Global mijoz (boshqa modullar shuni ishlatadi)
client = GeminiClient(config.GEMINI_API_KEYS, config.GEMINI_MODEL)
