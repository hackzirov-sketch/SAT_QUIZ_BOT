from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from ai.token_budget import TOKEN_LIMITS

logger = logging.getLogger('ai.cache')

CACHE_DIR = Path(__file__).resolve().parent / '.cache'
CACHE_DEFAULTS = {
    'extracted_questions': 86400 * 30,
    'explanation': 86400 * 7,
    'mistake_analysis': 86400 * 7,
    'desmos_solution': 86400 * 30,
    'classify': 86400 * 30,
    'image_description': 86400 * 30,
}


class AICache:
    def __init__(self, cache_dir: str | Path | None = None, ttl_overrides: dict | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = {**CACHE_DEFAULTS, **(ttl_overrides or {})}
        self._mem: dict[str, str] = {}

    def _key(self, prefix: str, *parts: str) -> str:
        raw = ':'.join(parts)
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f'{prefix}_{h}'

    def _path(self, key: str) -> Path:
        return self.cache_dir / f'{key}.json'

    def get(self, prefix: str, *parts: str) -> str | None:
        mem_key = self._key(prefix, *parts)
        if mem_key in self._mem:
            return self._mem[mem_key]
        path = self._path(mem_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            ttl = self.ttl.get(prefix, 86400)
            if time.time() - data['ts'] > ttl:
                path.unlink(missing_ok=True)
                return None
            result = data.get('value', '')
            self._mem[mem_key] = result
            return result
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, value: str, prefix: str, *parts: str):
        mem_key = self._key(prefix, *parts)
        self._mem[mem_key] = value
        path = self._path(mem_key)
        try:
            path.write_text(
                json.dumps({'ts': time.time(), 'value': value}, ensure_ascii=False),
                encoding='utf-8',
            )
        except OSError as e:
            logger.warning('cache write failed %s: %s', path, e)

    def get_json(self, prefix: str, *parts: str) -> Any:
        raw = self.get(prefix, *parts)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, value: Any, prefix: str, *parts: str):
        self.set(json.dumps(value, ensure_ascii=False), prefix, *parts)

    def clear_prefix(self, prefix: str):
        self._mem = {k: v for k, v in self._mem.items() if not k.startswith(f'{prefix}_')}
        count = 0
        for path in self.cache_dir.glob(f'{prefix}_*.json'):
            path.unlink()
            count += 1
        if count:
            logger.info('cleared %d cache entries for prefix %s', count, prefix)

    def clear_all(self):
        self._mem.clear()
        count = 0
        for path in self.cache_dir.glob('*.json'):
            path.unlink()
            count += 1
        logger.info('cleared all %d cache entries', count)

    def stats(self) -> dict[str, Any]:
        files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in files)
        prefixes: dict[str, int] = {}
        for f in files:
            p = f.stem.split('_')[0] if '_' in f.stem else 'unknown'
            prefixes[p] = prefixes.get(p, 0) + 1
        return {
            'total_entries': len(files),
            'total_size_bytes': total_size,
            'total_size_kb': round(total_size / 1024, 1),
            'by_prefix': dict(sorted(prefixes.items())),
            'cache_dir': str(self.cache_dir),
        }
