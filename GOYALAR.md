# G'oyalar va reja (yo'l xaritasi)

Raqobatchilar (Slaydly, slide.uz, Aislidebot) bilan solishtirib tuzildi. Ishni bosqichma-bosqich qilamiz:
har bosqich alohida ishlaydigan holatda tugaydi, keyin keyingisiga o'tamiz.

## ✅ 1-bosqich — Ishlaydigan bot (tayyor)
- Mavzu → til → slaydlar soni → dizayn → **bepul reja** → 2 000 so'm → `.pptx`
- 50 ta dizayn, karusel ko'rinishida tanlash
- Balans, sovg'a bonusi, do'st taklif qilish, qo'lda to'lov (chek + admin tasdiqi)

## 2-bosqich — Avtomatik to'lov va ishonch
- **Click / Payme** orqali avtomatik to'lov. Telegram Payments (BotFather → Payments → Click yoki Payme)
  orqali ulanadi. Buning uchun YaTT yoki MChJ va Click/Payme bilan shartnoma kerak.
  Shungacha karta + chek usuli ishlab turadi.
- To'lov paketlari: 5 000 / 10 000 / 20 000 so'm (20 000 da +10% bonus).
- Majburiy obuna (ixtiyoriy): bonus olish uchun kanalga a'zo bo'lish. Kanal o'sishi uchun yaxshi.
- **PDF** formatini ham yuborish (talabalar ko'pincha PDF topshiradi).

## 3-bosqich — Sifat (raqobatchilardan ustun bo'lish uchun)
- **Ma'ruzachi matni**: har slayd uchun "nima gapirish kerak" degan izoh (PowerPoint'dagi notes). Raqobatchilarda yo'q.
- **Rejani tahrirlash**: foydalanuvchi sarlavhani o'zgartirish, slayd qo'shish yoki o'chirish imkoniga ega bo'ladi.
- **Fanga mos dizayn**: mavzuni AI tahlil qiladi va mos 3 ta shablonni tavsiya qiladi.
- **AI chizgan rasmlar** (Premium): masalan FLUX (Replicate yoki fal.ai), bir rasm ~$0.003.
  Muqova va 2–3 asosiy slayd uchun. Narxi 4 000 so'm. Kod tayyor: `app/images.py` ga yangi manba qo'shiladi.
- Jadval va diagramma slaydlari (raqamli mavzular uchun).
- O'qituvchi uchun "Dars taqdimoti": dars maqsadi, savollar, uyga vazifa slaydlari.

## 4-bosqich — Sayt (veb-versiya)
- `taqdimot.uz` kabi domen. Telegram orqali kirish (Telegram Login Widget), shuning uchun balans bot bilan umumiy bo'ladi.
- Sahifalar: bosh sahifa (skrinshotdagi "Nima tayyorlaymiz?" kabi), shablonlar galereyasi, "Mening ishlarim", balans.
- Backend: FastAPI. `app/service.py` ni bot bilan birga ishlatadi, ya'ni AI va PPTX kodi bitta.
- Brauzerda slaydlarni ko'rish (PDF preview) va yuklab olish.

## 5-bosqich — Qo'shimcha xizmatlar (har biri alohida daromad)
| Xizmat | Taxminiy narx |
|---|---|
| Referat / mustaqil ish (DOCX) | 3 000 so'm |
| Test / viktorina (savol-javob, kalit bilan) | 1 500 so'm |
| Taqdimotni tarjima qilish (yuklangan .pptx) | 2 000 so'm |
| Konspekt (PDF/DOCX fayldan) | 2 000 so'm |
| Rezyume (CV) | 5 000 so'm |

## Marketing g'oyalari
- **Creator dasturi**: taklif qilgan do'stning to'lovlaridan 10–20% foiz. Hozir taklif uchun bir martalik bonus bor, keyin foizga o'tamiz.
- TikTok/Instagram uchun "30 soniyada taqdimot" videolari.
- Universitet va maktab Telegram guruhlariga promokodlar (`/promo KOD`).
- Imtihon va sessiya davrlarida (yanvar, may–iyun) aksiyalar.

## Ehtiyot bo'ling
- Ba'zi shablonlarda boshqa botning `@SlaytTop01_bot` yozuvi bor edi. Bot uni avtomatik olib tashlaydi,
  lekin shablonlar boshqa bot yoki saytdan olingan bo'lsa, ularni ishlatish huquqingiz borligini tekshiring.
  Eng xavfsiz yo'l: Slidesgo yoki SlidesCarnival kabi bepul litsenziyali shablonlar yoki o'zingiz chizgan dizaynlar.
