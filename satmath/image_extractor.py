from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig

logger = logging.getLogger(__name__)


class ImageExtractor:
    def __init__(self, pdf_path: Path | str = SATMathConfig.PDF_SOURCE):
        self.pdf_path = Path(pdf_path)
        self._fitz_available = False
        try:
            import fitz
            self._fitz = fitz
            self._fitz_available = True
        except ImportError:
            logger.warning('PyMuPDF not available. Use pip install PyMuPDF')

    def extract_page_images(self, output_dir: Path | None = None) -> dict[str, list[str]]:
        if not self._fitz_available:
            logger.error('PyMuPDF required for image extraction')
            return {}

        out = output_dir or SATMathConfig.PAGE_IMAGES_DIR
        out.mkdir(parents=True, exist_ok=True)

        doc = self._fitz.open(str(self.pdf_path))
        result = {}
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            fname = f'page_{page_num + 1:04d}.png'
            path = str(out / fname)
            pix.save(path)
            result[str(page_num + 1)] = [path]
        doc.close()
        logger.info('extracted %d page images to %s', len(result), out)
        return result

    def extract_page_region(self, page_num: int, rect: tuple[float, float, float, float],
                            output_path: Path) -> bool:
        if not self._fitz_available:
            return False
        doc = self._fitz.open(str(self.pdf_path))
        page = doc[page_num - 1]
        clip = self._fitz.Rect(*rect)
        pix = page.get_pixmap(dpi=300, clip=clip)
        pix.save(str(output_path))
        doc.close()
        return True

    def detect_image_regions(self, page_num: int) -> list[dict]:
        if not self._fitz_available:
            return []
        doc = self._fitz.open(str(self.pdf_path))
        page = doc[page_num - 1]
        images = page.get_images(full=True)
        regions = []
        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)
            w, h = base_image['width'], base_image['height']
            rects = page.get_image_rects(xref)
            for rect in rects:
                regions.append({
                    'xref': xref,
                    'width': w,
                    'height': h,
                    'rect': (rect.x0, rect.y0, rect.x1, rect.y1),
                })
        doc.close()
        return regions

    def build_images_manifest(self, questions: list[dict]) -> dict[str, Any]:
        manifest = {
            'source_pdf': str(self.pdf_path),
            'total_pages': 0,
            'extracted_images': [],
            'question_image_map': {},
            'missing_pages': [],
        }
        if not self.pdf_path.exists():
            return manifest

        try:
            import fitz
            doc = fitz.open(str(self.pdf_path))
            manifest['total_pages'] = len(doc)
            doc.close()
        except ImportError:
            return manifest

        existing = set()
        if SATMathConfig.PAGE_IMAGES_DIR.exists():
            existing = {f.stem for f in SATMathConfig.PAGE_IMAGES_DIR.glob('page_*.png')}

        for q in questions:
            page = q.get('page')
            if page:
                key = f'page_{int(page):04d}'
                if key in existing:
                    manifest['question_image_map'][q['id']] = str(SATMathConfig.PAGE_IMAGES_DIR / f'{key}.png')
                else:
                    manifest['missing_pages'].append(page)

        manifest['extracted_images'] = [str(f) for f in SATMathConfig.PAGE_IMAGES_DIR.glob('*.png')]
        return manifest
