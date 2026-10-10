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

> Railway loyihadagi `Dockerfile` bo'yicha yig'adi: Python + LibreOffice (slaydlar ko'rinishi va PDF uchun).
> Birinchi yig'ish 5–10 daqiqa davom etishi mumkin.

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

## Admin panel

- Botda `/admin` buyrug'i: statistika, «AI ishlayaptimi?» tekshiruvi va admin panelni ochish tugmasi.
- Saytda: `https://<sayt>/admin`. Unda tizim holati (AI kaliti, bot, Volume, Click), chek to'lovlarini
  tasdiqlash, foydalanuvchilar balansini o'zgartirish va oxirgi buyurtmalar bor.
- Admin bo'lish uchun botga `/myid` yozing va chiqqan raqamni Railway Variables'da `ADMIN_IDS` ga qo'ying.

## Telegram Mini App (bot ichida sayt)

Bot ishga tushganda chat pastidagi **menyu tugmasini** «Saytni ochish» qilib o'rnatadi.
Tugma saytni Telegram ichida ochadi va foydalanuvchini **avtomatik taniydi**: parol ham, kirish havolasi ham kerak emas.
Buning uchun sayt manzili ma'lum bo'lishi kifoya. Railway'da u `RAILWAY_PUBLIC_DOMAIN` orqali o'zi aniqlanadi.

Ishga tushgach tekshirish:
1. Botga `/start` yozing. Chat pastida (xabar yozish joyining chap tomonida) «Saytni ochish» tugmasi paydo bo'lishi kerak.
   Ko'rinmasa, Telegram'ni yopib qayta oching.
2. Tugmani bosing: sayt ochiladi, yuqorida ismingiz va balansingiz chiqadi.
3. Saytda taqdimot yarating. Fayl ham saytda yuklanadi, ham bot chatiga keladi.

## Click orqali avtomatik to'lov

Kod tayyor, faqat Click kalitlari kerak:
1. Click bilan shartnoma tuzing (YaTT yoki MChJ kerak): https://click.uz → «Biznes uchun» → onlayn to'lov qabul qilish.
2. Merchant kabinetida servis yarating va quyidagi manzillarni kiriting:
   - **Prepare URL:** `https://<sayt>/click/prepare`
   - **Complete URL:** `https://<sayt>/click/complete`
3. Kabinetdagi `service_id`, `merchant_id` va `secret_key` qiymatlarini Railway Variables'ga
   `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY` nomlari bilan qo'shing.

Shundan so'ng botda «Hisobni to'ldirish» va saytdagi narx bo'limida summa tugmalari chiqadi.
To'lov o'tishi bilan balans avtomatik to'ladi va bot xabar yuboradi. Karta + chek usuli zaxira sifatida qoladi.

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
| Telegram Mini App: bot menyusidan sayt, avtomatik kirish | ✅ |
| Saytga Telegram kodi bilan kirish (botda `/kod` yoki saytdagi tugma) | ✅ |
| Diagrammalar: botda «Ha/Yo'q», saytda «Diagramma» tugmasi (haqiqiy PowerPoint diagrammasi) | ✅ |
| Tayyor taqdimotni saytda tahrirlash: matn, rasm (yuklash yoki AI), diagramma, dizayn, shrift | ✅ |
| Tahrirlovchida slaydlarning haqiqiy ko'rinishi va PDF yuklab olish (LibreOffice, `Dockerfile`) | ✅ |
| Infografika: katta raqamlar, bosqichlar, vaqt chizig'i; premium uslubdagi diagrammalar | ✅ |
| Click orqali avtomatik to'lov (kalitlar qo'yilgach yoqiladi) | ✅ |
| Payme | ⏳ [GOYALAR.md](GOYALAR.md) |

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
