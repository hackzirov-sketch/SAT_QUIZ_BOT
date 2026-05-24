from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig


@dataclass
class QuestionRecord:
    id: str
    source_pdf: str
    page: int | None
    topic: str
    month: str
    question_number_original: int
    question_type: str
    difficulty: str
    sat_domain: str
    skill: str
    calculator_allowed: bool
    desmos_recommended: bool
    image_required: bool
    question_text: str
    choices: dict[str, str]
    correct_answer: str
    manual_solution_uz: str
    desmos_solution_uz: str
    shortcut_uz: str
    common_trap_uz: str
    tags: list[str]
    needs_manual_review: bool
    estimated_time_seconds: int = 60
    trap_level: str = 'low'


@dataclass
class MockTestRecord:
    test_id: str
    type: str
    label: str
    modules: list[dict]
    scoring: dict
    metadata: dict


@dataclass
class TopicPracticeRecord:
    type: str
    topic: str
    label: str
    total_questions: int
    questions: list[dict]


class DatabaseSchema:
    def __init__(self, output_dir: Path = SATMathConfig.OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_questions_json(self, questions: list[dict]) -> Path:
        path = self.output_dir / 'questions.json'
        cleaned = [self._clean_question(q) for q in questions]
        path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def export_mock_tests_json(self, tests: list[dict]) -> Path:
        path = self.output_dir / 'mock_tests.json'
        path.write_text(json.dumps(tests, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def export_metadata(self, **kwargs) -> Path:
        path = self.output_dir / 'metadata.json'
        path.write_text(json.dumps(kwargs, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def export_manifest(self, questions: list[dict], report: dict | None = None) -> Path:
        manifest = {
            'version': SATMathConfig.VERSION,
            'total_questions': len(questions),
            'multiple_choice': sum(1 for q in questions if q['question_type'] == 'multiple_choice'),
            'grid_in': sum(1 for q in questions if q['question_type'] == 'grid_in'),
            'topics': {},
            'domains': {},
            'difficulties': {},
            'files': {},
        }
        for q in questions:
            t = q.get('topic', 'Unknown')
            manifest['topics'][t] = manifest['topics'].get(t, 0) + 1
            d = q.get('sat_domain', 'Unknown')
            manifest['domains'][d] = manifest['domains'].get(d, 0) + 1
            diff = q.get('difficulty', 'easy')
            manifest['difficulties'][diff] = manifest['difficulties'].get(diff, 0) + 1

        for f in self.output_dir.glob('*.json'):
            manifest['files'][f.name] = f.stat().st_size

        if report:
            manifest['validation'] = report

        path = self.output_dir / 'manifest.json'
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def _clean_question(self, q: dict) -> dict:
        return {
            k: v for k, v in q.items()
            if k in QuestionRecord.__dataclass_fields__
        } if isinstance(q, dict) else q

    def build_sql_ddl(self) -> str:
        return """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    source_pdf TEXT NOT NULL DEFAULT 'Mathbook 3.0',
    page INTEGER,
    topic TEXT NOT NULL,
    month TEXT,
    question_number_original INTEGER,
    question_type TEXT NOT NULL DEFAULT 'multiple_choice',
    difficulty TEXT NOT NULL DEFAULT 'easy',
    sat_domain TEXT NOT NULL DEFAULT 'Algebra',
    skill TEXT,
    calculator_allowed INTEGER NOT NULL DEFAULT 1,
    desmos_recommended INTEGER NOT NULL DEFAULT 0,
    image_required INTEGER NOT NULL DEFAULT 0,
    question_text TEXT NOT NULL,
    choices TEXT,
    correct_answer TEXT NOT NULL,
    manual_solution_uz TEXT,
    desmos_solution_uz TEXT,
    shortcut_uz TEXT,
    common_trap_uz TEXT,
    tags TEXT,
    needs_manual_review INTEGER NOT NULL DEFAULT 0,
    estimated_time_seconds INTEGER NOT NULL DEFAULT 60,
    trap_level TEXT NOT NULL DEFAULT 'low',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_questions_domain ON questions(sat_domain);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(question_type);

CREATE TABLE IF NOT EXISTS mock_tests (
    test_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT,
    modules TEXT NOT NULL,
    scoring TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    answers TEXT,
    score INTEGER,
    total INTEGER,
    percentage REAL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topic_practice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    topic TEXT NOT NULL,
    questions TEXT,
    results TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
