from __future__ import annotations

from pathlib import Path

from bot.config import MOCK_IMAGES_DIR

# Keywords that indicate a question needs its source page image
IMG_KEYWORDS = [
    'figure', 'graph', 'scatterplot', 'scatter plot', 'diagram',
    'plot', 'chart', 'note: figure', 'not drawn to scale',
    'survey results', 'line graph', 'dot plot',
]


def needs_image(question: dict) -> bool:
    text = (question.get('question', '') + ' ' + ' '.join(question.get('choices', {}).values())).lower()
    return any(kw in text for kw in IMG_KEYWORDS)


def get_image_path(question: dict) -> Path | None:
    page = question.get('source_page')
    if not page:
        return None
    path = MOCK_IMAGES_DIR / f'page_{int(page):04d}.png'
    return path if path.exists() else None
