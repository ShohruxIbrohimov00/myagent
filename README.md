# Shohrux — Telegram AI Agent

Ochiq Telegram kanallarni kuzatib, qiziqarli postlarni **Gemini AI** orqali
"Shohrux" shaxsiyati tilida qayta yozadigan va **siz tasdiqlaganingizdan keyin**
o'z kanalingizga joylaydigan bot.

## Nimalarni qiladi
- 📥 Manba kanallardan yangi postlarni (matn + rasm) o'qiydi
- 🧠 Reklama / keraksiz kontentni ajratib tashlaydi
- 🔁 Bir xil yangilik bir nechta kanalda chiqsa — takrorlamaydi
- ✍️ Postni Shohrux uslubida, Telegram qoidalariga mos qayta yozadi
- ✅ Sizga tasdiq uchun yuboradi (tugma bilan: Tashlash / Yo'q)
- 🔑 10-20 ta Gemini API kalitini navbatma-navbat ishlatadi (limit tugasa keyingisiga o'tadi)

## Tuzilishi
| Fayl | Vazifasi |
|------|----------|
| `config.py` | Sozlamalar (.env dan) |
| `gemini_client.py` | Gemini + API kalit rotatsiyasi |
| `persona.py` | Shohrux shaxsiyati va AI ko'rsatmalari |
| `database.py` | SQLite (ko'rilgan/chop etilgan/kutilayotgan postlar) |
| `source_reader.py` | Telethon — manba kanallarni o'qish |
| `processor.py` | AI: filtr + dedup + qayta yozish |
| `bot.py` | Admin bot + tasdiqlash |
| `main.py` | Hammasini ulaydigan bosh fayl |

## O'rnatish

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ni to'ldiring (pastdagi izohga qarang)
python main.py
```

Birinchi ishga tushirishda Telethon **telefon raqamingiz va kod** so'raydi
(faqat bir marta — keyin `shohrux_session` faylida saqlanadi).

## .env ni qayerdan olish
- **BOT_TOKEN** — [@BotFather](https://t.me/BotFather)
- **ADMIN_ID** — [@userinfobot](https://t.me/userinfobot)
- **API_ID / API_HASH** — https://my.telegram.org → API development tools
- **GEMINI_API_KEYS** — https://aistudio.google.com/app/apikey (bir nechta hisobdan oling)
- **TARGET_CHANNEL** — o'z kanalingiz; botni o'sha kanalga **admin** qiling

## Tekin server (24/7 ishlashi uchun)
Tavsiya: **Oracle Cloud "Always Free"** VPS (uxlab qolmaydi). U yerda:
```bash
# screen yoki systemd orqali doimiy ishlatish
screen -S shohrux
python main.py
# Ctrl+A, keyin D bosib chiqib ketasiz
```
Muqobil: Fly.io yoki Railway (limitli soatlar bilan).

## Shohruxni o'zgartirish (admin panel)
Shaxsiyat endi **kodda emas, bazada** saqlanadi va botning o'zidan turib o'zgartiriladi:
- Botga `/start` (yoki `/panel`) yozing → **👤 Shaxsiyat** tugmasi
- **✏️ O'zgartirish** → yangi shaxsiyat matnini yuborasiz (kasbi, mahorati, fe'l-atvori, qadriyatlari, uslubi)
- **♻️ Standartga qaytarish** → tayyor standart shaxsiyatga qaytadi

Standart shaxsiyat `persona.py` ichidagi `DEFAULT_PERSONA` da yozilgan — birinchi
ishga tushganda shu ishlaydi, keyin paneldан xohlagancha o'zgartirasiz.
