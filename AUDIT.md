# YaratSlayd — texnik audit (2026-yil 10-oktabr)

Bu hujjatda loyihaning holati, topilgan kamchiliklar va ularning qaysilari tuzatilgani yozilgan.
Muhimlik darajasi: **P0** — pul, ma'lumot yoki qonun bilan bog'liq, birinchi navbatda; **P1** — keyingi navbat;
**P2** — keyinchalik.

## Nima tekshirilmagan (ochiq aytamiz)

- **Railway'dagi jonli sayt.** Bu muhitdan tashqi saytlarga kirish yopiq. Hamma narsa kompyuterdagi nusxada tekshirildi.
- **Haqiqiy Gemini/Groq/Claude.** API kaliti yo'q, testlar AI'ning DEMO rejimida va soxta (ataylab buzilgan)
  javoblar bilan o'tdi. Haqiqiy matn sifati, javob vaqti va xarajat o'lchanmagan.
- **Haqiqiy Telegram bot va Click to'lovi.** Click callbacklari imzo va takrorlanish bo'yicha test qilindi,
  lekin Click serveri bilan haqiqiy to'lov qilinmagan.
- **Pollinations/Pexels rasmlari.** Tarmoq yopiq, rasm sifati tekshirilmagan.
- **Haqiqiy PowerPoint.** Fayllar LibreOffice'da ochildi va PDF'ga aylantirildi. Microsoft PowerPoint'da
  ko'rinishi biroz farq qilishi mumkin.

## P0 — tuzatildi

| Muammo | Qayerda | Nima qilindi |
|---|---|---|
| Pul yechish va buyurtma ochish alohida amallar edi: o'rtada xato bo'lsa pul yechilib, buyurtma ochilmay qolardi | `app/web.py` generate, `bot.py` plan_ok | `db.start_order()` — ikkalasi bitta tranzaksiyada |
| Pul qaytarish bir martaligi kafolatlanmagan edi (`add_balance` istalgancha chaqirilishi mumkin edi) | `app/db.py` | `db.fail_order()` faqat `pending` va hali qaytarilmagan buyurtmaga ishlaydi (`orders.refunded`) |
| Server yarim yo'lda to'xtasa buyurtma abadiy `pending` qolar, pul qaytmasdi | `app/web.py` (holat faqat xotirada) | Ishga tushishda `service.recover_stuck_orders()` buyurtmani yopadi, pulni qaytaradi, bot foydalanuvchiga xabar beradi (`main.py`) |
| Server qayta ishga tushgach sayt «Topilmadi» deb qolardi | `/api/jobs/{id}` | Holat xotirada bo'lmasa bazadan olinadi |
| Botda xabar yuborishda xato bo'lsa pul qaytmasdi | `bot.py` plan_ok | Pul yechilgandan keyingi hamma qadam `try` ichida |
| 30 kunlik sessiya tokeni fayl havolalarida (`?s=`) yurardi — havola ulashilsa akkaunt ochilib qolardi | `app/sessions.py`, `web/index.html` | `?s=` qabul qilinmaydi. Fayl havolalarida 2 soatlik, faqat o'qish uchun imzolangan token (`?t=`) |
| AI'ning buzuq yoki to'liq bo'lmagan JSON javobi 500 xatoga olib kelardi | `app/ai.py` make_outline/make_content, clean_* | Har maydon tekshiriladi; bo'sh javobda tushunarli xato va pul qaytadi |
| Qimmat amallarga limit yo'q edi | AI rasm, rasm yuklash, qayta yig'ish | Soatlik limit: 20 / 40 / 60 (`web._limit`) |
| Bosh sahifadagi namuna «jonli» deb atalgan edi, «1–2 daqiqada» va «professional» va'dalari tekshirilmagan | `web/index.html` | «namuna» deb belgilandi, tekshirilmagan da'volar olib tashlandi. Haqiqiy o'rtacha vaqt admin panelda ko'rinadi |
| Foydalanuvchi o'z ma'lumotini o'chira olmasdi, maxfiylik siyosati yo'q edi | — | Taqdimotni o'chirish, «Barcha ma'lumotlarimni o'chirish», `/privacy` sahifasi |
| AI to'qigan raqamlar fakt sifatida berilardi | `app/ai.py` SYSTEM | Prompt: statistika, iqtibos, qonun va manba nomini to'qimaslik; noaniq raqam o'rniga sifat bilan tushuntirish. Tahrirlovchida «faktlarni tekshiring» ogohlantirishi |
| Bot xabarlarida AI sarlavhasi, reja va Telegram ismi HTML'ga ekranlanmasdan qo'yilardi: mavzu yoki ismda `<`, `&` bo'lsa Telegram xabarni rad etar, to'langan fayl yoki chek admin'ga yetib bormasdi | `bot.py`, `app/web.py` | `html.escape` |
| Avtomatik testlar yo'q edi | — | `tests/` — 30 ta test (pastda) |

## P0 — sizning qaroringiz kerak: shablonlar litsenziyasi

`scripts/qa_templates.py` shablon fayllarining ichini tekshirdi:

- **10 ta shablonda** (01, 03, 04, 05, 06, 07, 08, 09, 11, 12) boshqa botning yozuvi bor: `@SlaydTop01_bot`
  (turli imloda). Demak, bu shablonlar raqobatchi xizmatdan olingan. Kodda bu yozuv slayddan avtomatik
  o'chiriladi, lekin **yozuvni o'chirish litsenziya bo'lmaydi**. Ular bilan pul ishlash huquqiy xavf.
- **29-shablon** PresentationGO saytidan (`presentationgo.com`). Uning shartlari odatda shablonni taqdimotda
  ishlatishga ruxsat beradi, lekin qayta tarqatish yoki sotishni taqiqlaydi. Siz esa faylni har bir mijozga
  berasiz — shartlarini o'qib chiqish kerak.
- Qolgan 38 ta shablonda begona yozuv topilmadi. Lekin bu ularning manbasi toza degani emas: qayerdan
  olinganini siz bilasiz.

Tavsiya: manbasi aniq bo'lmagan shablonlarni o'zingiz chizgan yoki tijoriy litsenziyali (masalan, sotib olingan
yoki CC0) dizaynlar bilan almashtirish. Shungacha shubhali shablonlarni ro'yxatdan olib qo'yish mumkin —
buni sizning ruxsatingizsiz qilmadim, chunki bu 50 tadan 11 tasini yo'qotish degani.

## Shablonlar sifati (avtomatik tekshiruv natijasi)

Har bir shablonda 10 slaydlik og'ir sinov taqdimoti yig'ildi (uzun sarlavha, uzun punktlar, rasm, diagramma,
katta raqamlar, bosqichlar, vaqt chizig'i). Hisobot va rasmlar: `python scripts/qa_templates.py` →
`data/qa/report.md`, `data/qa/<id>.jpg`.

- 50 tadan 50 tasi xatosiz yig'ildi va LibreOffice'da ochildi, slaydlar soni to'g'ri.
- **31-shablon**: uzun muqova sarlavhasida taglavha slayd pastidan chiqib ketadi. Matn rangi juda och (kontrast past).
- **Hamma shablonda**: bitta slaydga ~900 belgidan ko'p matn tushsa, shrift ~11 pt gacha maydalashadi.
  Tuzatildi: AI matni bir slaydda ~620 belgi bilan cheklanadi (`ai.SLIDE_TEXT_BUDGET`).
- **16-shablon**: diagramma tor ustunga tushib, juda kichik chiqadi.
- **Bosqichlar va vaqt chizig'i** slaydlarida bitta qisqa punkt pastki burchakda yolg'iz qoladi (barcha shablonlarda).
- Ko'z bilan tekshirish baribir kerak: skript faqat aniq texnik nosozliklarni (chiqib ketgan va mayda matn,
  begona yozuv) topadi, dizayn chiroyli yoki xunukligini emas.

## P1 — keyingi navbat

| Muammo | Qayerda | Taklif |
|---|---|---|
| Baza zaxirasi yo'q: Volume buzilsa balanslar yo'qoladi | `data/bot.db` | Kunlik zaxira (masalan, admin botga `.db` faylni yuborishi) |
| Limitlar xotirada: server qayta ishga tushsa nolga tushadi | `app/web.py` | Hozirgi bitta server uchun yetarli. Bir nechta server bo'lsa bazaga ko'chirish |
| `/api/plan` bepul: AI limitini begona odam sarflab qo'yishi mumkin | `app/web.py` | Hozir IP/foydalanuvchiga soatiga 15 ta. Kerak bo'lsa reja uchun ham kirishni talab qilish |
| Haqiqiy xarajat va vaqt noma'lum | — | Admin panelda o'rtacha tayyorlanish vaqti endi ko'rinadi. AI tokenlari sonini ham yozib borish kerak |
| Manbalar yo'q | `app/ai.py` | Manbali rejim: foydalanuvchi bergan hujjat yoki havoladan olingan faktlar va oxirida «Manbalar» slaydi. AI manba nomini o'zi to'qimasligi kerak |
| Ma'ruzachi izohlari yo'q | `app/pptx_builder.py` | Har slayd ostiga nutq matni (PowerPoint «Notes») |
| Tahrirlovchida slayd qo'shish/o'chirish/tartiblash, avtosaqlash va «ortga qaytarish» yo'q | `web/index.html` | 3-bosqich rejasi |
| LibreOffice ko'p xotira oladi | `app/preview.py` | Bir vaqtda 2 tagacha render cheklangan. Railway rejasida xotirani kuzatish |

## P2 — keyinchalik

- PDF, DOCX va TXT hujjatdan taqdimot yaratish.
- Mavzuga qarab eng mos 3 ta dizayn tavsiyasi.
- Bitta slaydni AI orqali qayta yozdirish.
- Payme.
- Testlarni GitHub Actions'da avtomatik ishga tushirish.

## Testlar

`python -m pytest tests` — 30 ta test, ~10 soniya. Haqiqiy baza, AI, Telegram yoki pulga tegmaydi.

| Fayl | Nimani tekshiradi |
|---|---|
| `tests/test_orders.py` | muvaffaqiyatli generatsiya va bir marta pul yechish; mablag' yetmasa buyurtma ochilmaydi; AI xatosida pul bir marta qaytadi; ichki xato matni foydalanuvchiga ko'rinmaydi; bir vaqtda ikkita buyurtma yo'q; tugagan buyurtmaga pul qaytmaydi; server qayta ishga tushganda tiklash; pul yechish va buyurtma atomarligi |
| `tests/test_payments.py` | Click complete ikki marta kelsa balans bir marta to'ladi; noto'g'ri imzo va summa; bekor qilingan to'lov; chek bir marta tasdiqlanadi |
| `tests/test_access.py` | begona foydalanuvchi taqdimot, fayl, rasm, PDF, saqlash va o'chirishga kira olmaydi; kirmagan foydalanuvchi; URL'dagi sessiya rad etiladi; fayl tokeni faqat o'qish uchun, eskiradi, soxtasi ishlamaydi; boshqa saytdan POST; kirish kodi bir martalik |
| `tests/test_bot.py` | bot rejasi xabarida HTML ekranlanadi |
| `tests/test_editor.py` | tahrirlab saqlash yangi PPTX beradi; PDF va ko'rinish qayta yasaladi (LibreOffice bo'lsa); taqdimot va akkaunt ma'lumotlarini o'chirish; AI rasm limiti; AI'ning buzuq javoblari; punktlarni tozalash va matn chegarasi |

Testlarning o'zi ham tekshirildi: pul qaytarishdagi himoya va URL'dagi sessiya taqiqi ataylab buzilganda tegishli
testlar yiqildi.
