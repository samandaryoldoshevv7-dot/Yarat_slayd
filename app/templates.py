"""Shablonlar ro'yxati, turkumlari va ko'rinish rasmlari."""
from dataclasses import dataclass
from pathlib import Path

from . import config

CATEGORIES = {
    "minimal": "Minimal",
    "business": "Biznes",
    "education": "Ta'lim",
    "tech": "Texnologiya",
    "dark": "Qorong'i va hashamatli",
    "nature": "Tabiat",
    "creative": "Ijodiy",
}

# Har bir shablonning uslubi (previews/ dagi rasmlarga qarab ajratilgan)
_CATEGORY_OF = {
    "01": "minimal", "02": "business", "03": "dark", "04": "business", "05": "creative",
    "06": "minimal", "07": "business", "08": "tech", "09": "tech", "10": "creative",
    "11": "minimal", "12": "dark", "13": "nature", "14": "minimal", "15": "business",
    "16": "nature", "17": "creative", "18": "nature", "19": "education", "20": "education",
    "21": "nature", "22": "business", "23": "creative", "24": "business", "25": "business",
    "26": "dark", "27": "education", "28": "dark", "29": "tech", "30": "dark",
    "31": "nature", "32": "dark", "33": "tech", "34": "dark", "35": "tech",
    "36": "education", "37": "creative", "38": "dark", "39": "tech", "40": "education",
    "41": "minimal", "42": "minimal", "43": "creative", "44": "creative", "45": "creative",
    "46": "business", "47": "business", "48": "tech", "49": "tech", "50": "tech",
}


# Eng chiroylilari birinchi ko'rsatiladi (qolganlari raqam tartibida keyin)
FEATURED = ["13", "08", "02", "07", "34", "28", "16", "21", "18", "26", "30", "38", "46", "47", "50",
            "49", "33", "12", "04", "09", "20", "36", "44", "43", "37", "22", "35", "31", "45", "48"]


@dataclass(frozen=True)
class Template:
    id: str  # "01", "02", ...
    path: Path

    @property
    def preview(self) -> Path:
        return config.PREVIEWS_DIR / f"{self.id}.jpg"

    @property
    def category(self) -> str:
        return _CATEGORY_OF.get(self.id, "minimal")


def all_templates() -> list[Template]:
    out = []
    for p in sorted(config.TEMPLATES_DIR.glob("template_*.pptx")):
        out.append(Template(id=p.stem.split("_", 1)[1], path=p))
    rank = {tid: i for i, tid in enumerate(FEATURED)}
    return sorted(out, key=lambda t: (rank.get(t.id, len(rank)), t.id))


def get(template_id: str) -> Template | None:
    return next((t for t in all_templates() if t.id == template_id), None)
