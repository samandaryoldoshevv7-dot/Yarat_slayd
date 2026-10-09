"""Shablonlar ro'yxati va ularning ko'rinish rasmlari."""
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Template:
    id: str  # "01", "02", ...
    path: Path

    @property
    def preview(self) -> Path:
        return config.PREVIEWS_DIR / f"{self.id}.jpg"


def all_templates() -> list[Template]:
    out = []
    for p in sorted(config.TEMPLATES_DIR.glob("template_*.pptx")):
        out.append(Template(id=p.stem.split("_", 1)[1], path=p))
    return out


def get(template_id: str) -> Template | None:
    return next((t for t in all_templates() if t.id == template_id), None)
