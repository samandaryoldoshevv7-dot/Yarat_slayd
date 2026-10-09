# YaratSlayd — AI taqdimot boti va sayti

Foydalanuvchi mavzuni yozadi, AI reja tuzadi (bepul). Foydalanuvchi dizaynni tanlaydi va **2 000 so'm** to'laydi,
so'ng tayyor `.pptx` faylni oladi. **Telegram bot** va **sayt** bitta serverda ishlaydi, balans ikkalasi uchun umumiy.

## Qanday ishlaydi (oddiy tilda)

```
Foydalanuvchi ──► Telegram bot ─┐
                                ├──► Sizning serveringiz (Railway) ──► Gemini (matn, BEPUL)
Foydalanuvchi ──► Sayt ─────────┘         │                       └──► Pollinations (rasm, BEPUL)
                                          └──► 50 ta shablon asosida .pptx yig'iladi
```

- **Matnni** Google Gemini yozadi. Kalit bepul, kunlik limit bor.
- **Rasmlarni** Pollinations chizadi. Bepul, kalit ham kerak emas.
- **Faylni** serveringizdagi dastur shablon asosida yig'adi.
- Kalit qo'yilmasa bot **DEMO rejimda** ishlaydi: hammasi ishlaydi, faqat slaydlarga namuna matn yoziladi.

## Railway'ga joylash (qadamma-qadam)

1. **Gemini kaliti (bepul):** https://aistudio.google.com/apikey → Google akkaunt bilan kiring → **Create API key** → nusxalang.
2. **Bot tokeni:** Telegram'da @BotFather → `/newbot` → tokenni nusxalang.
3. **Admin ID:** @userinfobot ga yozing, u sizning raqamingizni beradi.
4. **Railway:** https://railway.com → **New Project** → **Deploy from GitHub repo** → `Yarat_slayd` ni tanlang.
5. Servisni oching → **Variables** bo'limiga qo'shing:

   | Nomi | Qiymati |
   |---|---|
   | `BOT_TOKEN` | BotFather bergan token |
   | `GEMINI_API_KEY` | AI Studio bergan kalit |
   | `ADMIN_IDS` | sizning Telegram ID'ingiz |
   | `PAYMENT_CARD` | to'lov qabul qiladigan karta raqami |
   | `PAYMENT_CARD_OWNER` | karta egasining ismi |

6. **Volume (ma'lumotlar o'chib ketmasligi uchun):** Railway'da loyihani oching (servislar turgan katta maydon).
   Bo'sh joyni o'ng tugma bilan bosing (yoki `Ctrl+K` / `⌘K` → «Volume» deb yozing) → **Create Volume** →
   servisingizni tanlang → **Mount path:** `/app/data` → **Create**. Railway servisni o'zi qayta ishga tushiradi.
   Volume bo'lmasa, har yangilanishda balanslar, to'lovlar va fayllar o'chadi.
7. **Sayt manzili:** servisni bosing → **Settings → Networking → Public Networking → Generate Domain**.
   `...up.railway.app` manzili chiqadi, sayt shu manzilda ochiladi. Botdagi «🌐 Saytda ochish» tugmasi
   ham shu manzilni avtomatik oladi (o'z domeningiz bo'lsa `SITE_URL` o'zgaruvchisini qo'shing).
8. **Deploy** tugmasini bosing. **Deployments → View logs** bo'limida `Bot ishga tushdi: @...` va `AI: gemini` yozuvlari chiqishi kerak.

Boshqa sozlamalar (narx, bonus, rasm manbasi) `.env.example` faylida izohlari bilan yozilgan.

## Kompyuterda ishga tushirish

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # .env ni to'ldiring
python main.py            # bot + sayt (http://localhost:8000)
# yoki faqat bot: python bot.py
```

## Narxlar va xarajat

| Xizmat | Narxi |
|---|---|
| Gemini (matn) | Bepul, lekin minutlik va kunlik limit bor (limitlarni AI Studio'da ko'rasiz). Limit yetmay qolsa billing yoqiladi, shunda bitta taqdimot ~100–200 so'm |
| Pollinations (rasm) | Bepul |
| Railway (server) | Bepul sinov krediti, keyin taxminan $5/oy |
| Claude (ixtiyoriy, pullik) | Oldindan to'lanadigan balans, oylik obuna emas. Bitta taqdimot ~30–1 300 so'm (modelga qarab) |

## Imkoniyatlar

| Qism | Holat |
|---|---|
| Bot: mavzu → til → slaydlar soni → dizayn → bepul reja → to'lov → `.pptx` | ✅ |
| Sayt: shu jarayon brauzerda, rejani tahrirlash, 7 uslubga ajratilgan 50 ta dizayn | ✅ |
| Bot ↔ sayt: saytda yasalgan fayl botga ham keladi, botdan saytga bir bosishda kirish | ✅ |
| Saytga Telegram orqali kirish (bot tasdiqlaydi), «Mening ishlarim» | ✅ |
| Balans, 2 000 so'm sovg'a, do'st taklifi uchun +500 so'm | ✅ |
| To'ldirish: karta + chek, admin bir tugma bilan tasdiqlaydi | ✅ |
| Xato bo'lsa pul avtomatik qaytadi | ✅ |
| Admin: `/stats`, `/add <id> <summa>`, `/broadcast` (xabarga reply qilib) | ✅ |
| Click/Payme orqali avtomatik to'lov | ⏳ [GOYALAR.md](GOYALAR.md) |

## Tuzilishi

```
main.py                Bot + sayt birga (Railway shuni ishga tushiradi)
bot.py                 Telegram bot (aiogram 3)
app/web.py             Sayt serveri (FastAPI)
web/index.html         Sayt sahifasi
web/static/            Logo, favicon va namuna slaydlar (scripts/make_showcase.py yasaydi)
app/ai.py              AI: Gemini / Claude / DEMO
app/images.py          Rasmlar: Pollinations / Pexels
app/pptx_builder.py    Shablon asosida .pptx yig'ish
app/service.py         Umumiy generatsiya (bot va sayt uchun)
app/db.py              SQLite: foydalanuvchilar, balans, buyurtmalar, to'lovlar, sayt sessiyalari
templates/             50 ta .pptx shablon
previews/              Shablonlarning ko'rinish rasmlari
web/old_frontend.html  Eski sayt (AI'siz namuna, ishlatilmaydi)
```

Yangi shablon qo'shsangiz (`templates/template_51.pptx`), ko'rinish rasmini qayta yarating
(LibreOffice va poppler-utils kerak): `python scripts/make_previews.py`
