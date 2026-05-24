from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAT_MATH_DOMAINS = [
    'Algebra',
    'Advanced Math',
    'Problem Solving and Data Analysis',
    'Geometry and Trigonometry',
]

SUBTOPICS = [
    'Expressions', 'Linear Equations', 'Systems of Equations',
    'Linear Functions', 'Linear Inequalities',
    'Polynomials', 'Exponents & Radicals', 'Function Notation',
    'Exponential Functions', 'Quadratics',
    'Percent / Ratio / Proportion', 'Unit Conversion',
    'Probability', 'Mean / Median / Mode / Range',
    'Scatterplots', 'Margin of Error / Outliers',
    'Lines and Angles', 'Triangles', 'Trigonometry',
    'Circles', 'Area and Volume',
]

DOMAIN_MAP: dict[str, str] = {
    'Expressions': 'Algebra',
    'Linear Equations': 'Algebra',
    'Systems of Equations': 'Algebra',
    'Linear Functions': 'Algebra',
    'Linear Inequalities': 'Algebra',
    'Polynomials': 'Advanced Math',
    'Exponents & Radicals': 'Advanced Math',
    'Function Notation': 'Advanced Math',
    'Exponential Functions': 'Advanced Math',
    'Quadratics': 'Advanced Math',
    'Percent / Ratio / Proportion': 'Problem Solving and Data Analysis',
    'Unit Conversion': 'Problem Solving and Data Analysis',
    'Probability': 'Problem Solving and Data Analysis',
    'Mean / Median / Mode / Range': 'Problem Solving and Data Analysis',
    'Scatterplots': 'Problem Solving and Data Analysis',
    'Margin of Error / Outliers': 'Problem Solving and Data Analysis',
    'Lines and Angles': 'Geometry and Trigonometry',
    'Triangles': 'Geometry and Trigonometry',
    'Trigonometry': 'Geometry and Trigonometry',
    'Circles': 'Geometry and Trigonometry',
    'Area and Volume': 'Geometry and Trigonometry',
}

CHOICES = ('A', 'B', 'C', 'D')

MOCK_MODULE_1_SIZE = 22
MOCK_MODULE_2_SIZE = 22
MOCK_TOTAL = 44
MODULE_TIME_MINUTES = 35
MODULE_TIME_SECONDS = MODULE_TIME_MINUTES * 60

QUESTION_TYPES = ('multiple_choice', 'grid_in')

DIFFICULTY_LEVELS = ('easy', 'medium', 'hard')
TRAP_LEVELS = ('low', 'medium', 'high')

SAT_TOPIC_ALIASES: dict[str, str] = {
    'Exponents&Radicals': 'Exponents & Radicals',
    'Functions&Function Notation': 'Function Notation',
    'Linear System of Equations': 'Systems of Equations',
    'Mean, Median, Mode, Range': 'Mean / Median / Mode / Range',
    'Percent, Ratio & Proportion': 'Percent / Ratio / Proportion',
    'Percent; Ratio&Proportion': 'Percent / Ratio / Proportion',
    'Research Organizing': 'Margin of Error / Outliers',
    'Research organizing(Margin of Error; Outliers)': 'Margin of Error / Outliers',
}

SCORING_RULES: dict[str, Any] = {
    'total_questions': 44,
    'module_1_size': 22,
    'module_2_size': 22,
    'module_1_max_raw': 22,
    'module_2_max_raw': 22,
    'max_raw_score': 44,
    'min_scaled_score': 200,
    'max_scaled_score': 800,
    'hard_module_bonus': 30,
    'easy_module_cap': 720,
    'raw_to_scaled': {},
}


class SATMathConfig:
    VERSION: str = '1.1.0'
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    SATMATH_DIR: Path = PROJECT_ROOT / 'satmath'
    DATA_DIR: Path = SATMATH_DIR / 'data'
    PDF_SOURCE: Path = PROJECT_ROOT / 'bot' / 'data' / 'mock_pdfs' / 'Mathbook 3.0.pdf'
    EXISTING_BANK: Path = PROJECT_ROOT / 'bot' / 'data' / 'mock_tests' / 'math_mock_bank.json'
    EXTRACTED_TEXT: Path = PROJECT_ROOT / 'bot' / 'data' / 'mock_tests' / 'extracted' / 'Mathbook 3.0.txt'
    MOCK_IMAGES_DIR: Path = PROJECT_ROOT / 'bot' / 'data' / 'mock_images'
    PAGE_MAPPING: Path = PROJECT_ROOT / 'bot' / 'data' / 'mock_images' / 'page_mapping.json'
    MOCK_HISTORY: Path = DATA_DIR / 'mock_history.json'
    OUTPUT_DIR: Path = DATA_DIR

    OUTPUT_QUESTIONS: Path = DATA_DIR / 'questions.json'
    OUTPUT_ANSWER_KEYS: Path = DATA_DIR / 'answer_keys.json'
    OUTPUT_TOPICS: Path = DATA_DIR / 'topics.json'
    OUTPUT_MOCK_TESTS: Path = DATA_DIR / 'mock_tests.json'
    OUTPUT_IMAGES_MANIFEST: Path = DATA_DIR / 'images_manifest.json'
    OUTPUT_SCORING_RULES: Path = DATA_DIR / 'scoring_rules.json'
    OUTPUT_PAGE_MAP: Path = DATA_DIR / 'page_map.json'
    OUTPUT_QA_REPORT: Path = DATA_DIR / 'qa_report.json'
    OUTPUT_DATABASE: Path = DATA_DIR / 'sat_math.db'

    QUESTION_IMAGES_DIR: Path = DATA_DIR / 'assets' / 'questions'
    DIAGRAM_IMAGES_DIR: Path = DATA_DIR / 'assets' / 'diagrams'
    PAGE_IMAGES_DIR: Path = DATA_DIR / 'assets' / 'pages'

    @classmethod
    def ensure_dirs(cls):
        for d in [cls.DATA_DIR, cls.QUESTION_IMAGES_DIR, cls.DIAGRAM_IMAGES_DIR, cls.PAGE_IMAGES_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_existing_bank(cls) -> list[dict]:
        if cls.EXISTING_BANK.exists():
            return json.loads(cls.EXISTING_BANK.read_text(encoding='utf-8'))
        return []

    @classmethod
    def load_page_mapping(cls) -> dict[str, list[str]]:
        if cls.PAGE_MAPPING.exists():
            return json.loads(cls.PAGE_MAPPING.read_text(encoding='utf-8'))
        return {}
