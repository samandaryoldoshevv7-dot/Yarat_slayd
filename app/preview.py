"""Slaydlarning haqiqiy ko'rinishi (PNG/JPG) va PDF — LibreOffice orqali.

Serverda LibreOffice bo'lmasa (masalan, Dockerfile'siz deploy) funksiyalar bo'sh natija qaytaradi,
sayt esa ko'rinishsiz (faqat matn) rejimda ishlashda davom etadi.
"""
import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

# LibreOffice ko'p xotira oladi — bir vaqtda 2 tadan ortiq render qilinmaydi
_slots = asyncio.Semaphore(2)


def available() -> bool:
    return bool(shutil.which("soffice") and shutil.which("pdftoppm"))


async def _run(*cmd: str, timeout: int = 150) -> bool:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        log.warning("Vaqt tugadi: %s", cmd[0])
        return False
    if proc.returncode != 0:
        log.warning("%s xatosi: %s", cmd[0], (err or b"").decode(errors="ignore")[:300])
        return False
    return True


async def render(pptx: Path, out_dir: Path, dpi: int = 60) -> list[Path]:
    """pptx -> out_dir/deck.pdf va out_dir/s-1.jpg, s-2.jpg, ... Muvaffaqiyatsiz bo'lsa []."""
    if not available():
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    async with _slots:
        with tempfile.TemporaryDirectory() as tmp:
            # Har render alohida LibreOffice profili bilan — parallel ishlaganda to'qnashmaydi
            profile = Path(tmp) / f"lo_{uuid.uuid4().hex}"
            ok = await _run("soffice", f"-env:UserInstallation=file://{profile}", "--headless",
                            "--convert-to", "pdf", "--outdir", tmp, str(pptx))
            pdf = Path(tmp) / (pptx.stem + ".pdf")
            if not ok or not pdf.exists():
                return []
            shutil.move(str(pdf), out_dir / "deck.pdf")
        ok = await _run("pdftoppm", "-r", str(dpi), "-jpeg", "-jpegopt", "quality=82",
                        str(out_dir / "deck.pdf"), str(out_dir / "s"))
        if not ok:
            return []
    files = sorted(out_dir.glob("s-*.jpg"), key=lambda p: int(p.stem.split("-")[-1]))
    # pdftoppm nomlarni s-01 / s-1 ko'rinishida beradi — bir xil qilamiz
    out = []
    for i, f in enumerate(files, 1):
        target = out_dir / f"{i}.jpg"
        f.rename(target)
        out.append(target)
    return out
