"""Shablon (.pptx) asosida tayyor taqdimot yig'ish.

Shablondagi namuna slaydlar o'chiriladi, dizayn (master/layout) saqlanib qoladi va
AI matni shu layoutlar asosida yangi slaydlarga joylanadi.
"""
import copy
import io
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

TITLE_TYPES = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}
BODY_TYPES = {PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.SUBTITLE}
LABELS = {
    "uz": {"agenda": "Reja", "thanks": "E'tiboringiz uchun rahmat!"},
    "ru": {"agenda": "План", "thanks": "Спасибо за внимание!"},
    "en": {"agenda": "Agenda", "thanks": "Thank you for your attention!"},
}


def _ph_types(layout) -> list:
    return [ph.placeholder_format.type for ph in layout.placeholders]


def _has_title(layout) -> bool:
    return any(t in TITLE_TYPES for t in _ph_types(layout))


def _has_body(layout) -> bool:
    return any(t in BODY_TYPES for t in _ph_types(layout))


def _title_on_top(layout) -> bool:
    """Sarlavha matn maydonidan yuqorida joylashgan oddiy layoutmi."""
    title = next((p for p in layout.placeholders if p.placeholder_format.type in TITLE_TYPES), None)
    body = next((p for p in layout.placeholders if p.placeholder_format.type == PP_PLACEHOLDER.OBJECT), None)
    if title is None or body is None or title.top is None or body.top is None:
        return True
    return title.top + title.height // 2 < body.top


def _pick_layouts(prs) -> dict:
    used = [s.slide_layout for s in prs.slides]
    # Ba'zi shablonlarda bir nechta master bor — dizayn namuna slaydlar ishlatgan masterda
    main = used[0].slide_master if used else prs.slide_master
    layouts = list(main.slide_layouts) + [
        l for m in prs.slide_masters if m is not main for l in m.slide_layouts
    ]

    def first(cands, pred):
        return next((l for l in cands if pred(l)), None)

    is_cover = lambda l: PP_PLACEHOLDER.CENTER_TITLE in _ph_types(l)  # noqa: E731
    is_content = lambda l: (  # noqa: E731
        PP_PLACEHOLDER.TITLE in _ph_types(l) and PP_PLACEHOLDER.OBJECT in _ph_types(l)
        and _ph_types(l).count(PP_PLACEHOLDER.OBJECT) == 1
    )
    cover = first(used, is_cover) or first(used[:1], _has_title) or first(layouts, is_cover) or layouts[0]

    content = []
    for l in used:
        if is_content(l) and _title_on_top(l) and all(l is not c for c in content):
            content.append(l)
    if not content:
        content = [first(layouts, is_content) or first(layouts, lambda l: _has_title(l) and _has_body(l))]

    closing = first(layouts, lambda l: l.name.lower() == "closing" and _has_title(l)) or cover
    return {"cover": cover, "content": content, "closing": closing}


def _capture_decor(slide) -> list:
    """Namuna slayddagi matnsiz bezaklarni (fon rasmlari, shakllar) saqlab oladi."""
    items = []
    for sh in slide.shapes:
        if sh.is_placeholder or (sh.has_text_frame and sh.text_frame.text.strip()):
            continue
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            items.append(("pic", sh.image.blob, sh.left, sh.top, sh.width, sh.height))
        elif not sh._element.xpath(".//@r:embed | .//@r:id | .//@r:link"):
            items.append(("xml", copy.deepcopy(sh._element)))
    return items


def _apply_decor(slide, items) -> None:
    tree = slide.shapes._spTree
    pos = 2  # nvGrpSpPr va grpSpPr dan keyin — ya'ni eng orqa qatlam
    for item in items:
        if item[0] == "pic":
            _, blob, left, top, w, h = item
            el = slide.shapes.add_picture(io.BytesIO(blob), left, top, w, h)._element
        else:
            el = copy.deepcopy(item[1])
        tree.remove(el) if el.getparent() is tree else None
        tree.insert(pos, el)
        pos += 1


def _remove_all_slides(prs) -> None:
    sld_ids = prs.slides._sldIdLst
    for sld_id in list(sld_ids):
        prs.part.drop_rel(sld_id.rId)
        sld_ids.remove(sld_id)


def _strip_watermarks(prs) -> None:
    """Shablon mualliflarining '@..._bot' yozuvlarini master va layoutlardan olib tashlaydi."""
    parts = list(prs.slide_masters) + [l for m in prs.slide_masters for l in m.slide_layouts]
    for part in parts:
        for shape in list(part.shapes):
            if shape.has_text_frame and "_bot" in shape.text_frame.text:
                if shape.is_placeholder:
                    shape.text_frame.text = ""  # placeholderni o'chirsak dizayn buziladi
                else:
                    shape._element.getparent().remove(shape._element)


def _title_ph(slide):
    return next((p for p in slide.placeholders if p.placeholder_format.type in TITLE_TYPES), None)


def _body_phs(slide):
    phs = [p for p in slide.placeholders if p.placeholder_format.type in BODY_TYPES]
    return sorted(phs, key=lambda p: -(p.width or 0) * (p.height or 0))


def _clean_empty(slide) -> None:
    for ph in list(slide.placeholders):
        if ph.has_text_frame and not ph.text_frame.text.strip():
            ph._element.getparent().remove(ph._element)
        elif ph.placeholder_format.type == PP_PLACEHOLDER.PICTURE:
            ph._element.getparent().remove(ph._element)


def _set_text(ph, text: str, size: int | None = None) -> None:
    tf = ph.text_frame
    tf.text = text
    tf.word_wrap = True
    if size:
        for p in tf.paragraphs:
            for r in p.runs:
                r.font.size = Pt(size)


def _set_bullets(ph, bullets: list[str], size: int) -> None:
    tf = ph.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = b
        run.font.size = Pt(size)
        p.space_after = Pt(6)


def _bullet_size(bullets: list[str], narrow: bool) -> int:
    chars = sum(len(b) for b in bullets)
    size = 20 if chars < 280 else 18 if chars < 420 else 16 if chars < 560 else 14
    return size - 2 if narrow else size


def _add_picture_right(slide, body, image: bytes, slide_w: int) -> None:
    """O'ng tomonga rasm qo'yadi (4:3, markazdan kesib).

    Matn maydoni slaydning chap qismida bo'lsa, rasm bo'sh o'ng tomonga joylanadi,
    aks holda matn maydoni toraytiriladi.
    """
    from PIL import Image

    left, top, width, height = body.left, body.top, body.width, body.height
    gap = Emu(Pt(18))
    margin = int(slide_w * 0.05)
    if left + width < slide_w * 0.66:
        area_left, area_w = left + width + gap, slide_w - margin - (left + width + gap)
    else:
        text_w = int(width * 0.55)
        body.left, body.top, body.width, body.height = left, top, text_w, height
        area_left, area_w = left + text_w + gap, width - text_w - gap

    pic_w, pic_h = area_w, int(area_w * 3 / 4)
    if pic_h > height:
        pic_h, pic_w = height, int(height * 4 / 3)
    pic_left = area_left + (area_w - pic_w) // 2
    pic_top = top + (height - pic_h) // 2

    with Image.open(io.BytesIO(image)) as im:
        iw, ih = im.size
    pic = slide.shapes.add_picture(io.BytesIO(image), pic_left, pic_top, pic_w, pic_h)
    box, img = pic_w / pic_h, iw / ih
    if img > box:  # rasm kengroq — yon tomonlardan kesamiz
        cut = (1 - box / img) / 2
        pic.crop_left = pic.crop_right = cut
    else:
        cut = (1 - img / box) / 2
        pic.crop_top = pic.crop_bottom = cut


def _title_size(ph, text: str, cover: bool) -> int:
    """Sarlavha o'lchami: matn uzunligi va eng uzun so'z maydonga sig'ishi bo'yicha."""
    n = len(text)
    if cover:
        size = 44 if n <= 28 else 40 if n <= 45 else 34 if n <= 70 else 28
    else:
        size = 32 if n <= 40 else 28 if n <= 60 else 24
    width_pt = (ph.width or 0) / 12700
    longest = max((len(w) for w in text.split()), default=1)
    if width_pt:
        size = min(size, int(width_pt / (longest * 0.58)))
    return max(size, 16)


def build(template: Path, out: Path, lang: str, outline: dict, content: dict, images: list | None = None) -> Path:
    prs = Presentation(str(template))
    lay = _pick_layouts(prs)
    slides = list(prs.slides)
    decor_for = lambda layout, default=None: next(  # noqa: E731
        (_capture_decor(sl) for sl in slides if sl.slide_layout is layout), default or []
    )
    cover_decor = _capture_decor(slides[0]) if slides and slides[0].slide_layout is lay["cover"] else []
    content_decor = [decor_for(l) for l in lay["content"]]
    closing_decor = decor_for(lay["closing"]) if lay["closing"] is not lay["cover"] else cover_decor
    _remove_all_slides(prs)
    _strip_watermarks(prs)
    labels = LABELS.get(lang, LABELS["uz"])
    images = images or [None] * len(content["slides"])

    # 1. Muqova
    s = prs.slides.add_slide(lay["cover"])
    _apply_decor(s, cover_decor)
    if (t := _title_ph(s)) is not None:
        _set_text(t, outline["title"], _title_size(t, outline["title"], cover=True))
    if (b := _body_phs(s)) and outline.get("subtitle"):
        _set_text(b[0], outline["subtitle"])
    _clean_empty(s)

    def content_slide(i, title, bullets, image=None):
        k = i % len(lay["content"])
        s = prs.slides.add_slide(lay["content"][k])
        _apply_decor(s, content_decor[k])
        if (t := _title_ph(s)) is not None:
            _set_text(t, title, _title_size(t, title, cover=False))
        body = _body_phs(s)
        if body:
            if image:
                try:
                    _add_picture_right(s, body[0], image, prs.slide_width)
                except Exception:  # buzilgan rasm butun taqdimotni to'xtatmasin
                    image = None
            _set_bullets(body[0], bullets, _bullet_size(bullets, narrow=bool(image)))
        _clean_empty(s)

    # 2. Reja
    content_slide(0, labels["agenda"], [f"{i}. {t}" for i, t in enumerate(outline["slides"], 1)])

    # 3. Asosiy slaydlar
    for i, sl in enumerate(content["slides"], 1):
        content_slide(i, sl["title"], sl["bullets"], images[i - 1] if i - 1 < len(images) else None)

    # 4. Yakuniy slayd
    s = prs.slides.add_slide(lay["closing"])
    _apply_decor(s, closing_decor)
    if (t := _title_ph(s)) is not None:
        _set_text(t, labels["thanks"], _title_size(t, labels["thanks"], cover=True))
    if (b := _body_phs(s)) and content.get("closing"):
        _set_text(b[0], content["closing"])
    _clean_empty(s)

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out
