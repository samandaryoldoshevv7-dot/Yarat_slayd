"""AI matn generatsiyasi. Ikki bosqich: reja (bepul) va to'liq matn (pullik).

Provayder config.AI_PROVIDER bo'yicha tanlanadi:
  gemini — Google Gemini (bepul limit bilan), claude — Anthropic Claude, demo — kalitsiz sinov.
"""
import asyncio
import json
import logging

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
    "Raqamlar, sanalar, misollar keltiring, lekin ishonchingiz komil bo'lmagan aniq statistikani to'qimang. "
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


class AIError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, timeout=180.0)
    return _client


async def _ask_json(prompt: str, schema: dict, max_tokens: int) -> dict:
    if config.AI_PROVIDER == "gemini":
        return await _ask_gemini(prompt, schema, max_tokens)
    return await _ask_claude(prompt, schema, max_tokens)


# ---------------- Gemini (REST) ----------------

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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
    models = [config.GEMINI_MODEL] + [m for m in ("gemini-flash-latest",) if m != config.GEMINI_MODEL]
    timeout = aiohttp.ClientTimeout(total=180)
    last_error = "AI xatosi"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in models:
            for attempt in range(3):
                try:
                    async with session.post(
                        GEMINI_URL.format(model=model),
                        params={"key": config.GEMINI_API_KEY},
                        json=body,
                    ) as r:
                        data = await r.json(content_type=None)
                        status = r.status
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    log.warning("Gemini ulanish xatosi: %s", e)
                    last_error = "AI serveriga ulanib bo'lmadi"
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                if status == 200:
                    return _parse_gemini(data)
                msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
                log.warning("Gemini %s (%s): %s", status, model, msg[:300])
                if status == 404:  # model nomi eskirgan — keyingisini sinaymiz
                    break
                if status in (429, 500, 502, 503, 504):
                    last_error = "AI hozir band (bepul limit), birozdan so'ng urinib ko'ring"
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                if status in (401, 403) or "API key" in msg or "API_KEY" in msg:
                    raise AIError("Gemini kaliti noto'g'ri yoki ruxsat yo'q (GEMINI_API_KEY ni tekshiring)")
                if status == 400:
                    raise AIError(f"AI so'rovi qabul qilinmadi: {msg[:150]}")
                raise AIError(f"AI xatosi ({status})")
    raise AIError(last_error)


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
    slides = [s.strip() for s in data["slides"] if s.strip()][:n]
    if not slides:
        raise AIError("Reja bo'sh chiqdi")
    return {"title": data["title"].strip() or topic, "subtitle": data["subtitle"].strip(), "slides": slides}


async def make_content(topic: str, lang: str, outline: dict) -> dict:
    if config.DEMO_MODE:
        return _demo_content(outline)
    titles = "\n".join(f"{i}. {t}" for i, t in enumerate(outline["slides"], 1))
    prompt = (
        f"Mavzu: {topic}\nTaqdimot sarlavhasi: {outline['title']}\nTil: {LANGS[lang]}\n\n"
        f"Quyidagi reja bo'yicha har bir slayd uchun matn yozing, tartib va sarlavhalarni saqlang:\n{titles}\n\n"
        "Har slaydga 4–5 ta mazmunli punkt. image_query — shu slaydga mos fotosurat qidirish uchun "
        "2–4 so'zli INGLIZCHA ibora (masalan 'solar panels field'). closing — yakuniy slayd uchun bitta "
        f"qisqa xulosa jumla. Matn {LANGS[lang]} da bo'lsin."
    )
    data = await _ask_json(prompt, CONTENT_SCHEMA, 16000)
    slides = []
    for i, title in enumerate(outline["slides"]):
        s = data["slides"][i] if i < len(data["slides"]) else {"bullets": [], "image_query": ""}
        bullets = [b.strip() for b in s["bullets"] if b.strip()][:6]
        slides.append({"title": s.get("title") or title, "bullets": bullets, "image_query": s["image_query"]})
    return {"slides": slides, "closing": data["closing"].strip()}


# ---------------- DEMO rejim ----------------

def _demo_outline(topic: str, n: int) -> dict:
    base = ["Kirish", "Mavzuning dolzarbligi", "Asosiy tushunchalar", "Tarixiy rivojlanish",
            "Hozirgi holat", "Muammolar va yechimlar", "Amaliy misollar", "Istiqbollar"]
    slides = [base[i % len(base)] for i in range(n - 1)] + ["Xulosa"]
    return {"title": topic.strip().capitalize(), "subtitle": "Taqdimot", "slides": slides[:n]}


def _demo_content(outline: dict) -> dict:
    slides = [
        {
            "title": t,
            "bullets": [f"{t} bo'yicha {k}-muhim fikr: bu yerda AI yozgan haqiqiy matn bo'ladi" for k in range(1, 5)],
            "image_query": "education",
        }
        for t in outline["slides"]
    ]
    return {"slides": slides, "closing": "DEMO rejim: ANTHROPIC_API_KEY qo'shilgach haqiqiy matn chiqadi."}
