from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    started_at: float = field(default_factory=time.time)
    polling_started: bool = False
    polling_alive: bool = False
    flask_alive: bool = False
    scheduler_alive: dict[str, bool] = field(default_factory=dict)
    vocabulary_count: int = 0
    last_db_check_ok: bool = False
    last_db_check_at: float = 0.0
    last_db_error: str = ''
    render_disk_mounted: bool | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            'uptime_seconds': max(0, int(time.time() - self.started_at)),
            'polling_started': self.polling_started,
            'polling_alive': self.polling_alive,
            'flask_alive': self.flask_alive,
            'scheduler_alive': dict(self.scheduler_alive),
            'vocabulary_count': self.vocabulary_count,
            'last_db_check_ok': self.last_db_check_ok,
            'last_db_check_at': self.last_db_check_at,
            'last_db_error': self.last_db_error,
            'render_disk_mounted': self.render_disk_mounted,
            'pid': os.getpid(),
        }


runtime_state = RuntimeState()
