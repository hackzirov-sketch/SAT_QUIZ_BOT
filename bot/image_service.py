from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from bot.config import RENDERED_IMAGES_DIR

logger = logging.getLogger(__name__)

IMAGE_OUTPUT_DIR = RENDERED_IMAGES_DIR

_HAS_PDF2IMAGE = False
_HAS_PYMUPDF = False

try:
    import fitz

    _HAS_PYMUPDF = True
except ImportError:
    try:
        from pdf2image import convert_from_path

        _HAS_PDF2IMAGE = True
    except ImportError:
        pass


def _ensure_dir() -> Path:
    IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_OUTPUT_DIR


def pdf_to_images(pdf_path: str | Path, dpi: int = 200) -> list[str]:
    if not _HAS_PYMUPDF and not _HAS_PDF2IMAGE:
        logger.warning('no_pdf_to_image_library_available')
        return []

    out_dir = _ensure_dir()
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.warning('pdf_not_found path=%s', pdf_path)
        return []

    output_paths = []
    stem = pdf_path.stem

    try:
        if _HAS_PYMUPDF:
            doc = fitz.open(str(pdf_path))
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi)
                img_path = str(out_dir / f'{stem}_page_{i + 1}.png')
                pix.save(img_path)
                output_paths.append(img_path)
            doc.close()
        elif _HAS_PDF2IMAGE:
            images = convert_from_path(str(pdf_path), dpi=dpi)
            for i, img in enumerate(images):
                img_path = str(out_dir / f'{stem}_page_{i + 1}.png')
                img.save(img_path, 'PNG')
                output_paths.append(img_path)

        logger.info('pdf_to_images_converted pages=%s path=%s', len(output_paths), pdf_path)
        return output_paths

    except Exception:
        logger.exception('pdf_to_image_failed path=%s', pdf_path)
        return []


def text_to_image_fallback(text: str, output_path: str | Path | None = None) -> str | None:
    try:
        from PIL import Image, ImageDraw, ImageFont

        lines = text.split('\n')
        font_size = 18
        line_height = font_size + 6
        margin = 20
        width = 800
        height = max(200, len(lines) * line_height + margin * 2)

        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype('arial.ttf', font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

        y = margin
        for line in lines:
            draw.text((margin, y), line, fill='black', font=font)
            y += line_height

        out_path = Path(str(output_path or _ensure_dir() / 'text_fallback.png'))
        img.save(out_path, 'PNG')
        logger.info('text_to_image_done path=%s', out_path)
        return str(out_path)

    except ImportError:
        logger.warning('pillow_not_installed_text_to_image_unavailable')
        return None
    except Exception:
        logger.exception('text_to_image_failed')
        return None


def cleanup_old_images(max_age_hours: int = 24):
    if not IMAGE_OUTPUT_DIR.exists():
        return
    from datetime import datetime

    now = datetime.now()
    for f in IMAGE_OUTPUT_DIR.iterdir():
        if f.is_file() and f.suffix in ('.png', '.jpg', '.jpeg'):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if (now - mtime).total_seconds() > max_age_hours * 3600:
                    f.unlink()
            except Exception:
                pass
