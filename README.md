# YaratSlayd — AI taqdimot boti

Foydalanuvchi mavzuni yozadi, bot reja tuzadi (bepul). Foydalanuvchi dizaynni tanlaydi va
**2 000 so'm** to'laydi, so'ng tayyor `.pptx` faylni oladi. Faylni PowerPoint, WPS yoki Google Slides'da tahrirlash mumkin.

## Hozir nima ishlaydi (1-bosqich)

| Qism | Holat |
|---|---|
| Telegram bot: mavzu → til (uz/ru/en) → slaydlar soni (5–20) → dizayn → reja → to'lov → fayl | ✅ |
| AI matn: Claude (avval reja, keyin to'liq matn) | ✅ |
| 50 ta shablon, har biri uchun ko'rinish rasmi (`previews/`) | ✅ |
| Slaydlarga rasm (Pexels, bepul fotobank) | ✅ |
| Balans, yangi foydalanuvchiga 2 000 so'm bonus, do'st taklif qilganga +500 | ✅ |
| Hisobni to'ldirish: karta orqali o'tkazma + chek, admin bir tugma bilan tasdiqlaydi | ✅ |
| Xato bo'lsa pul avtomatik qaytadi | ✅ |
| «Mening ishlarim»: eski fayllarni qayta yuklab olish | ✅ |
| Admin: `/stats`, `/add <id> <summa>`, `/broadcast` (xabarga reply qilib) | ✅ |
| Sayt (veb-versiya) | ⏳ 2-bosqich — [GOYALAR.md](GOYALAR.md) |

## Ishga tushirish

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # keyin .env ni to'ldiring
python bot.py
```

### Kalitlarni qayerdan olish

1. **BOT_TOKEN**: Telegram'da @BotFather → `/newbot`.
2. **ADMIN_IDS**: @userinfobot ga yozing, u sizning ID raqamingizni beradi.
3. **ANTHROPIC_API_KEY** (AI matn): https://console.anthropic.com → Billing (karta bilan $5–10 to'ldiriladi) → API Keys.
   Kalit bo'lmasa bot **DEMO rejimda** ishlaydi: hamma narsa ishlaydi, faqat slaydlarda namuna matn chiqadi.
4. **PEXELS_API_KEY** (rasmlar, bepul): https://www.pexels.com/api/ → ro'yxatdan o'ting → kalitni nusxalang.

### AI xarajati (bitta taqdimot, taxminan)

Bitta taqdimotga ~1 000 ta kirish va ~3 000–5 000 ta chiqish tokeni ketadi.

| `CLAUDE_MODEL` | 1 ta taqdimot | 2 000 so'mdan qoladigan foyda |
|---|---|---|
| `claude-opus-5-5` (standart, eng sifatli) | ≈ $0.06–0.10 (≈ 800–1 300 so'm) | ≈ 700–1 200 so'm |
| `claude-sonnet-5-5` | ≈ $0.03–0.05 (≈ 400–650 so'm) | ≈ 1 350–1 600 so'm |
| `claude-haiku-5-5` (eng arzon) | ≈ $0.002–0.003 (≈ 30 so'm) | ≈ 1 970 so'm |

Pexels rasmlari bepul. Maslahat: 10–20 ta sinov taqdimot yasab, `claude-haiku-5-5` matnining sifati
sizni qoniqtirsa, shunga o'ting. Model nomini `.env` da almashtirish kifoya.

### Ko'rinish rasmlarini qayta yaratish

Shablon qo'shsangiz (`templates/template_51.pptx` kabi nomlang), ko'rinish rasmini qayta yarating:

```bash
sudo apt install libreoffice poppler-utils   # bir marta
python scripts/make_previews.py
```

## Tuzilishi

```
bot.py                 Telegram bot (aiogram 3)
app/config.py          .env sozlamalari
app/ai.py              Claude: reja va matn (DEMO rejim ham shu yerda)
app/images.py          Rasmlar (Pexels)
app/pptx_builder.py    Shablon asosida .pptx yig'ish
app/service.py         Umumiy generatsiya (bot va sayt uchun)
app/db.py              SQLite: foydalanuvchilar, balans, buyurtmalar, to'lovlar
app/templates.py       Shablonlar ro'yxati
templates/             50 ta .pptx shablon
previews/              Shablonlarning ko'rinish rasmlari
web/old_frontend.html  Eski sayt (AI'siz, faqat namuna uchun saqlab qo'yildi)
```

Serverga qo'yish: 1 GB RAM'li har qanday VPS yetadi (Hetzner, DigitalOcean, mahalliy hosting).
`systemd` yoki `tmux` orqali `python bot.py` doimiy ishlab tursin.
