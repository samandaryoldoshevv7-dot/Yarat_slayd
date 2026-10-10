"""AI matn generatsiyasi. Ikki bosqich: reja (bepul) va to'liq matn (pullik).

Provayder config.AI_PROVIDER bo'yicha tanlanadi:
  gemini — Google Gemini (bepul limit bilan), claude — Anthropic Claude, demo — kalitsiz sinov.
"""
import asyncio
import json
import logging
import time

import aiohttp

from . import config

log = logging.getLogger(__name__)

LANGS = {
    "uz": "o'zbek tili (lotin yozuvi)",
    "ru": "русский язык",
    "en": "English",
}

# Rad etilganda boshqa modelga avtomatik o'tish (server-side fallback) shu modellarda bor
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

SYSTEM = (
    "Siz O'zbekistondagi talaba va o'qituvchilar uchun taqdimot (slayd) tayyorlaydigan tajribali "
    "muallifsiz. Matn aniq, faktlarga asoslangan, akademik va tushunarli bo'lsin. "
    "Har bir punkt qisqa (8–18 so'z), takrorlanmasin, umumiy 'suv' gaplar bo'lmasin. "
    "Faqat berilgan mavzu doirasida yozing, bir fikrni turli slaydlarda takrorlamang. "
    "Faqat keng ma'lum va ishonchli fakt, sana va raqamlarni keltiring; aniq qiymatni bilmasangiz, raqam o'rniga "
    "sifat bilan tushuntiring yoki 'taxminan' deb yaxlitlang. Hech qachon statistika, iqtibos, qonun raqami, "
    "tadqiqot yoki manba nomini o'ylab topmang. "
    "Javobni faqat so'ralgan JSON sxemasida bering."
)

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "slides": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "subtitle", "slides"],
    "additionalProperties": False,
}

CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "image_query": {"type": "string"},
                },
                "required": ["title", "bullets", "image_query"],
                "additionalProperties": False,
            },
        },
        "closing": {"type": "string"},
    },
    "required": ["slides", "closing"],
    "additionalProperties": False,
}


# Diagramma yoqilganda har slaydga qo'shimcha maydonlar (Gemini "ixtiyoriy" maydonni yaxshi
# qo'llamagani uchun hamma slaydda bor, keraksizlarida chart_type = "none")
CHART_FIELDS = {
    "chart_type": {"type": "string"},
    "chart_title": {"type": "string"},
    "chart_labels": {"type": "array", "items": {"type": "string"}},
    "chart_values": {"type": "array", "items": {"type": "number"}},
    "chart_unit": {"type": "string"},
    # Infografika: "text" (oddiy), "stats" (katta raqamlar), "steps" (bosqichlar), "timeline" (vaqt chizig'i)
    "layout": {"type": "string"},
    "items": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "value": {"type": "string"}, "text": {"type": "string"}},
            "required": ["label", "value", "text"],
            "additionalProperties": False,
        },
    },
}


def _content_schema(charts: bool) -> dict:
    if not charts:
        return CONTENT_SCHEMA
    import copy

    schema = copy.deepcopy(CONTENT_SCHEMA)
    item = schema["properties"]["slides"]["items"]
    item["properties"].update(CHART_FIELDS)
    item["required"] += list(CHART_FIELDS)
    return schema


MAX_CHARTS = 3
MAX_INFOGRAPHICS = 3
LAYOUTS = ("stats", "steps", "timeline")


def clean_layout(s: dict) -> tuple[str | None, list | None]:
    """AI bergan infografikani tekshiradi: (layout, items) yoki (None, None)."""
    layout = str(s.get("layout") or "").lower().strip()
    if layout not in LAYOUTS:
        return None, None
    items = []
    raw = s.get("items")
    for it in (raw if isinstance(raw, list) else [])[:5 if layout != "stats" else 4]:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label") or "").strip()[:60]
        value = str(it.get("value") or "").strip()[:24]
        text = str(it.get("text") or "").strip()[:160]
        if layout == "stats" and value and label:
            items.append({"label": label, "value": value, "text": ""})
        elif layout != "stats" and label:
            items.append({"label": label, "value": "", "text": text})
    if len(items) < 2:
        return None, None
    return layout, items


def clean_chart(s: dict) -> dict | None:
    """AI bergan diagramma ma'lumotini tekshiradi; yaroqsiz bo'lsa None."""
    kind = str(s.get("chart_type") or s.get("type") or "").lower().strip()
    if kind not in ("column", "bar", "pie", "line"):
        return None
    raw_labels = s.get("chart_labels") or s.get("labels") or []
    raw_values = s.get("chart_values") or s.get("values") or []
    if not isinstance(raw_labels, list) or not isinstance(raw_values, list):
        return None
    labels = [str(x).strip()[:40] for x in raw_labels]
    try:
        values = [float(v) for v in raw_values]
    except (TypeError, ValueError):
        return None
    n = min(len(labels), len(values), 8)
    if n < 2 or not all(labels[:n]):
        return None
    values = [int(v) if float(v).is_integer() else round(v, 2) for v in values[:n]]
    return {"type": kind, "title": str(s.get("chart_title") or s.get("title") or "")[:80],
            "labels": labels[:n], "values": values, "unit": str(s.get("chart_unit") or s.get("unit") or "")[:20]}


class AIError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, timeout=180.0)
    return _client


# Oxirgi AI xatosi — admin paneldagi "AI tekshiruvi" uchun
last_error: dict = {}


def _remember(provider: str, model: str, status, message: str) -> None:
    last_error.update(provider=provider, model=model, status=status, message=message[:500],
                      time=time.strftime("%Y-%m-%d %H:%M:%S"))


async def _ask_json(prompt: str, schema: dict, max_tokens: int) -> dict:
    if config.AI_PROVIDER == "claude":
        return await _ask_claude(prompt, schema, max_tokens)
    try:
        return await _ask_gemini(prompt, schema, max_tokens)
    except AIError:
        # Gemini bepul limiti tugasa — Groq (bepul) zaxira sifatida
        if config.GROQ_API_KEY:
            log.warning("Gemini ishlamadi, Groq'ga o'tilmoqda")
            return await _ask_groq(prompt, schema, max_tokens)
        raise


# ---------------- Gemini (REST) ----------------

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Bitta model limiti tugasa yoki ishlamasa, keyingisi sinaladi (har birining bepul limiti alohida)
GEMINI_FALLBACKS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest",
                    "gemini-flash-lite-latest", "gemini-2.0-flash"]


def _gemini_schema(schema: dict) -> dict:
    """JSON Schema -> Gemini responseSchema (OpenAPI uslubi, additionalProperties'siz)."""
    out = {"type": schema["type"].upper()}
    if "properties" in schema:
        out["properties"] = {k: _gemini_schema(v) for k, v in schema["properties"].items()}
        out["required"] = schema.get("required", [])
        out["propertyOrdering"] = list(schema["properties"])
    if "items" in schema:
        out["items"] = _gemini_schema(schema["items"])
    return out


async def _ask_gemini(prompt: str, schema: dict, max_tokens: int) -> dict:
    if not config.GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY qo'yilmagan")
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(schema),
            # 2.5+ modellarda "o'ylash" tokenlari ham shu limitga kiradi
            "maxOutputTokens": max(max_tokens * 2, 8192),
            "temperature": 0.7,
        },
    }
    models = list(dict.fromkeys([config.GEMINI_MODEL] + GEMINI_FALLBACKS))
    timeout = aiohttp.ClientTimeout(total=120)
    user_error = "AI hozir javob bermayapti. Bir daqiqadan so'ng qayta urinib ko'ring."
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in models:
            for attempt in range(2):
                try:
                    async with session.post(
                        GEMINI_URL.format(model=model), params={"key": config.GEMINI_API_KEY}, json=body
                    ) as r:
                        data = await r.json(content_type=None)
                        status = r.status
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    _remember("gemini", model, "network", str(e) or type(e).__name__)
                    log.warning("Gemini ulanish xatosi (%s): %s", model, e)
                    await asyncio.sleep(2)
                    continue
                if status == 200:
                    try:
                        return _parse_gemini(data)
                    except AIError as e:
                        _remember("gemini", model, 200, str(e))
                        log.warning("Gemini javobi yaroqsiz (%s): %s", model, e)
                        break  # keyingi model
                msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else str(data)[:300]
                _remember("gemini", model, status, msg)
                log.warning("Gemini %s (%s): %s", status, model, msg[:300])
                if status in (401, 403) or "API key" in msg or "API_KEY" in msg:
                    raise AIError("Gemini kaliti noto'g'ri yoki bloklangan. Admin GEMINI_API_KEY ni tekshirishi kerak.")
                if status == 429:
                    break  # bu modelning limiti tugagan — darhol keyingi modelga
                if status in (500, 502, 503, 504):
                    await asyncio.sleep(3)
                    continue
                break  # 400/404 va boshqalar — keyingi model
    raise AIError(user_error)


# ---------------- Groq (bepul zaxira, OpenAI uslubidagi API) ----------------

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _ask_groq(prompt: str, schema: dict, max_tokens: int) -> dict:
    body = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt + "\n\nJavob faqat shu JSON sxemaga mos JSON obyekt bo'lsin:\n"
             + json.dumps(schema, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "max_tokens": min(max_tokens, 8000),
    }
    timeout = aiohttp.ClientTimeout(total=120)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GROQ_URL, json=body,
                                    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}) as r:
                data = await r.json(content_type=None)
                status = r.status
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        _remember("groq", config.GROQ_MODEL, "network", str(e))
        raise AIError("AI serveriga ulanib bo'lmadi") from e
    if status != 200:
        msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
        _remember("groq", config.GROQ_MODEL, status, msg)
        raise AIError("AI hozir javob bermayapti. Bir daqiqadan so'ng qayta urinib ko'ring.")
    try:
        return json.loads(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        _remember("groq", config.GROQ_MODEL, 200, "JSON o'qilmadi")
        raise AIError("AI javobini o'qib bo'lmadi, qayta urinib ko'ring") from e


async def health_check() -> dict:
    """Admin uchun: AI haqiqatan javob beryaptimi?"""
    started = time.time()
    try:
        data = await _ask_json("Bitta so'z bilan javob bering: salom", {
            "type": "object", "properties": {"answer": {"type": "string"}},
            "required": ["answer"], "additionalProperties": False}, 200)
        return {"ok": True, "provider": config.AI_PROVIDER, "seconds": round(time.time() - started, 1),
                "answer": str(data.get("answer", ""))[:50]}
    except AIError as e:
        return {"ok": False, "provider": config.AI_PROVIDER, "error": str(e), "last_error": dict(last_error)}


def _parse_gemini(data: dict) -> dict:
    cands = data.get("candidates") or []
    if not cands:
        raise AIError("AI bu mavzuda javob bermadi, mavzuni boshqacha yozib ko'ring")
    cand = cands[0]
    if cand.get("finishReason") == "MAX_TOKENS":
        raise AIError("Javob juda uzun chiqdi, slaydlar sonini kamaytiring")
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError("AI javobini o'qib bo'lmadi, qayta urinib ko'ring") from e


# ---------------- Claude ----------------

async def _ask_claude(prompt: str, schema: dict, max_tokens: int) -> dict:
    import anthropic

    params = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
    )
    client = _get_client()
    try:
        if config.CLAUDE_MODEL in _FALLBACK_MODELS:
            resp = await client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
            )
        else:
            resp = await client.messages.create(**params)
    except anthropic.RateLimitError as e:
        raise AIError("AI hozir band, birozdan so'ng urinib ko'ring") from e
    except anthropic.APIStatusError as e:
        log.exception("Claude API xatosi")
        raise AIError(f"AI xatosi ({e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise AIError("AI serveriga ulanib bo'lmadi") from e

    if resp.stop_reason == "refusal":
        raise AIError("AI bu mavzuda taqdimot tayyorlashni rad etdi")
    if resp.stop_reason == "max_tokens":
        raise AIError("Javob juda uzun chiqdi, slaydlar sonini kamaytiring")
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError("AI javobini o'qib bo'lmadi") from e


def content_count(total_slides: int) -> int:
    """Umumiy slaydlardan muqova, reja va yakuniy slayd ayiriladi."""
    return max(1, total_slides - 3)


async def make_outline(topic: str, lang: str, total_slides: int) -> dict:
    n = content_count(total_slides)
    if config.DEMO_MODE:
        return _demo_outline(topic, n)
    prompt = (
        f"Mavzu: {topic}\nTil: {LANGS[lang]}\n\n"
        f"Shu mavzuda taqdimot rejasini tuzing: aniq {n} ta slayd sarlavhasi (kirish, asosiy qismlar, "
        f"oxirgisi xulosa). Shuningdek taqdimot sarlavhasi (mavzuning chiroyli ifodasi) va qisqa "
        f"taglavha. Hammasi {LANGS[lang]} da bo'lsin."
    )
    data = await _ask_json(prompt, OUTLINE_SCHEMA, 2000)
    raw = data.get("slides") if isinstance(data, dict) else None
    slides = [" ".join(str(s).split())[:200] for s in (raw if isinstance(raw, list) else []) if str(s).strip()][:n]
    if not slides:
        raise AIError("AI reja tuzmadi, qayta urinib ko'ring")
    title = " ".join(str(data.get("title") or "").split())[:300] or topic
    return {"title": title, "subtitle": " ".join(str(data.get("subtitle") or "").split())[:300], "slides": slides}


async def make_content(topic: str, lang: str, outline: dict, charts: bool = False) -> dict:
    if config.DEMO_MODE:
        return _demo_content(outline, charts)
    titles = "\n".join(f"{i}. {t}" for i, t in enumerate(outline["slides"], 1))
    prompt = (
        f"Mavzu: {topic}\nTaqdimot sarlavhasi: {outline['title']}\nTil: {LANGS[lang]}\n\n"
        f"Quyidagi reja bo'yicha har bir slayd uchun matn yozing, tartib va sarlavhalarni saqlang:\n{titles}\n\n"
        "Har slaydga 4–5 ta mazmunli punkt. image_query — shu slayd uchun rasm tavsifi INGLIZCHA, 6–12 so'z, "
        "aniq va real sahna (masalan 'wind turbines on green hills at sunset, wide shot'), matnsiz. closing — yakuniy slayd uchun bitta "
        f"qisqa xulosa jumla. Matn {LANGS[lang]} da bo'lsin."
    )
    if charts:
        prompt += (
            "\n\nINFOGRAFIKA (layout): ko'pchilik slaydlar layout=\"text\". Mazmuniga mos 2–3 ta slaydga: "
            "\"stats\" — 2–4 ta muhim raqam (items: value='7,2 mln t', label='yillik maishiy chiqindi'); "
            "\"steps\" — 3–5 bosqichli jarayon (items: label='Saralash', text='bir jumlali izoh'); "
            "\"timeline\" — 3–5 sanali voqealar (items: label='1991', text='qisqa izoh'). "
            "Infografikali slaydlarda ham bullets'da 2–3 qisqa punkt bo'lsin. Faqat ishonchli raqam va sanalar."
        )
        prompt += (
            f"\n\nDIAGRAMMALAR: raqamli taqqoslash tabiiy bo'lgan 1–{MAX_CHARTS} ta slaydga diagramma qo'shing "
            "(chart_type: column — taqqoslash, bar — reyting, pie — ulushlar (yig'indisi 100), line — yillar bo'yicha "
            "o'zgarish). chart_labels 3–6 ta qisqa nom, chart_values shuncha raqam, chart_unit (masalan '%', 'mln', "
            "'yil'), chart_title qisqa. Faqat umumma'lum va ishonchli taxminiy ma'lumotlardan foydalaning, aniq raqam "
            "noma'lum bo'lsa diagramma qo'ymang. Diagrammasiz slaydlarda chart_type = \"none\", qolgan chart "
            "maydonlari bo'sh."
        )
    data = await _ask_json(prompt, _content_schema(charts), 16000)
    slides = []
    seen: set[str] = set()
    raw = data.get("slides") if isinstance(data, dict) else None
    raw = raw if isinstance(raw, list) else []
    for i, title in enumerate(outline["slides"]):
        s = raw[i] if i < len(raw) and isinstance(raw[i], dict) else {}
        bullets = clean_bullets(s.get("bullets"), seen)
        chart = clean_chart(s) if charts else None
        layout, items = clean_layout(s) if charts else (None, None)
        slides.append({"title": str(s.get("title") or title)[:200], "bullets": bullets,
                       "image_query": str(s.get("image_query") or title)[:200],
                       "chart": chart, "layout": layout, "items": items})
    # Juda ko'p diagramma yoki infografika bo'lsa ortiqchasini olib tashlaymiz
    charts_seen = info_seen = 0
    for sl in slides:
        if sl["chart"]:
            charts_seen += 1
            if charts_seen > MAX_CHARTS:
                sl["chart"] = None
        if sl["layout"]:
            info_seen += 1
            # Bosqich/vaqt chizig'i diagramma bilan bir slaydga sig'maydi
            if info_seen > MAX_INFOGRAPHICS or (sl["chart"] and sl["layout"] != "stats") or \
                    (sl["chart"] and sl["layout"] == "stats"):
                sl["layout"], sl["items"] = None, None
    if not any(sl["bullets"] for sl in slides):
        raise AIError("AI to'liq javob bermadi, qayta urinib ko'ring")
    closing = data.get("closing") if isinstance(data, dict) else ""
    return {"slides": slides, "closing": str(closing or "").strip()[:400]}


MAX_BULLET = 220  # belgidan uzun punkt slaydga sig'maydi
# Bitta slayddagi jami matn. Ko'pi shriftni ~11 pt gacha maydalaydi (scripts/qa_templates.py hamma shablonda
# shuni ko'rsatdi), shuning uchun oxirgi punktlar tashlanadi
SLIDE_TEXT_BUDGET = 620


def clean_bullets(items, seen: set[str] | None = None, limit: int = 6) -> list[str]:
    """AI punktlarini tozalaydi: bo'sh, takroriy (butun taqdimot bo'yicha) va haddan tashqari uzunlarini."""
    out = []
    seen = seen if seen is not None else set()
    for b in items if isinstance(items, list) else []:
        b = " ".join(str(b).split()).lstrip("•-–* ").strip()
        if not b:
            continue
        if len(b) > MAX_BULLET:
            b = b[:MAX_BULLET].rsplit(" ", 1)[0].rstrip(",;:") + "…"
        key = b.lower().rstrip(".…")
        if key in seen:
            continue
        if out and sum(map(len, out)) + len(b) > SLIDE_TEXT_BUDGET:
            break
        seen.add(key)
        out.append(b)
        if len(out) == limit:
            break
    return out


# ---------------- DEMO rejim ----------------

def _demo_outline(topic: str, n: int) -> dict:
    base = ["Kirish", "Mavzuning dolzarbligi", "Asosiy tushunchalar", "Tarixiy rivojlanish",
            "Hozirgi holat", "Muammolar va yechimlar", "Amaliy misollar", "Istiqbollar"]
    slides = [base[i % len(base)] for i in range(n - 1)] + ["Xulosa"]
    return {"title": topic.strip().capitalize(), "subtitle": "Taqdimot", "slides": slides[:n]}


def _demo_content(outline: dict, charts: bool = False) -> dict:
    slides = [
        {
            "title": t,
            "bullets": [f"{t} bo'yicha {k}-muhim fikr: bu yerda AI yozgan haqiqiy matn bo'ladi" for k in range(1, 5)],
            "image_query": "education",
            "chart": None, "layout": None, "items": None,
        }
        for t in outline["slides"]
    ]
    if charts and len(slides) > 2:
        slides[2]["layout"] = "stats"
        slides[2]["items"] = [{"label": "yillik maishiy chiqindi", "value": "7,2 mln t", "text": ""},
                              {"label": "qayta ishlanadigan ulush", "value": "30%", "text": ""},
                              {"label": "o'sish sur'ati", "value": "4,6%", "text": ""}]
    if charts and len(slides) > 4:
        slides[4]["layout"] = "steps"
        slides[4]["items"] = [{"label": l, "value": "", "text": "Bosqichning qisqa izohi shu yerda"}
                              for l in ("Yig'ish", "Saralash", "Qayta ishlash", "Sotish")]
    if charts and len(slides) > 5:
        slides[5]["layout"] = "timeline"
        slides[5]["items"] = [{"label": y, "value": "", "text": "Muhim voqea qisqacha"}
                              for y in ("1991", "2005", "2017", "2026")]
    if charts and len(slides) > 1:
        slides[1]["chart"] = {"type": "column", "title": "Namuna diagramma", "unit": "%",
                              "labels": ["2022", "2023", "2024", "2025"], "values": [18, 27, 41, 56]}
    if charts and len(slides) > 3:
        slides[3]["chart"] = {"type": "pie", "title": "Ulushlar", "unit": "%",
                              "labels": ["A", "B", "C"], "values": [50, 30, 20]}
    return {"slides": slides, "closing": "DEMO rejim: ANTHROPIC_API_KEY qo'shilgach haqiqiy matn chiqadi."}
