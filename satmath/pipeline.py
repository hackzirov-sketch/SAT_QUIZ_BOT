from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig
from satmath.pdf_analyzer import PDFAnalyzer
from satmath.question_extractor import QuestionExtractor
from satmath.image_extractor import ImageExtractor
from satmath.answer_matcher import AnswerMatcher
from satmath.classifier import SATClassifier
from satmath.difficulty import DifficultyLabeler
from satmath.desmos_detector import DesmosDetector
from satmath.explanation_generator import ExplanationGenerator
from satmath.mistake_analysis import MistakeAnalyzer
from satmath.mock_generator import MockGenerator
from satmath.scoring_engine import ScoringEngine
from satmath.topic_practice import TopicPracticeGenerator
from satmath.database_schema import DatabaseSchema
from satmath.validator import QuestionValidator

logger = logging.getLogger('satmath.pipeline')


class Pipeline:
    def __init__(self, pdf_path: Path | str = SATMathConfig.PDF_SOURCE,
                 output_dir: Path | None = None):
        self.pdf_path = Path(pdf_path)
        self.output_dir = output_dir or SATMathConfig.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.extracted_text: str = ''
        self.questions: list[dict] = []
        self.mock_tests: list[dict] = []
        self.report: dict[str, Any] = {}
        self.validation: dict[str, Any] = {}

    def run(self, extract_questions: bool = True,
            classify: bool = True,
            label_difficulty: bool = True,
            detect_desmos: bool = True,
            generate_explanations: bool = True,
            generate_mocks: bool = True,
            num_mocks: int = 3,
            export: bool = True,
            validate: bool = True) -> dict[str, Any]:
        logger.info('Pipeline started — PDF: %s', self.pdf_path)

        if extract_questions:
            self._step_extract()
        if classify:
            self._step_classify()
        if label_difficulty:
            self._step_label_difficulty()
        if detect_desmos:
            self._step_detect_desmos()
        if generate_explanations:
            self._step_explanations()
        if generate_mocks and self.questions:
            self._step_generate_mocks(num_mocks)
        if validate:
            self._step_validate()
        if export:
            self._step_export()

        self.report['status'] = 'completed'
        self.report['total_questions'] = len(self.questions)
        self.report['mock_tests'] = len(self.mock_tests)
        self._save_pipeline_report()
        logger.info('Pipeline completed — %d questions, %d mock tests',
                    len(self.questions), len(self.mock_tests))
        return self.report

    def _step_extract(self):
        if not self.pdf_path.exists():
            logger.warning('PDF not found, checking for extracted text')
            if SATMathConfig.EXTRACTED_TEXT.exists():
                self.extracted_text = SATMathConfig.EXTRACTED_TEXT.read_text(encoding='utf-8')
            else:
                logger.error('No PDF or extracted text found')
                return
        else:
            analyzer = PDFAnalyzer(str(self.pdf_path))
            analysis = analyzer.analyze()
            self.report['pdf_analysis'] = {
                'total_pages': analysis.get('total_pages', 0),
                'topics_found': list(analysis.get('topics_found', {})),
                'topics_missing': analysis.get('topics_missing', []),
            }
            self.extracted_text = analyzer.extract_text()

        extractor = QuestionExtractor(self.extracted_text)
        self.questions = extractor.extract_all()

        self.report['extraction'] = {
            'multiple_choice': len(extractor.questions),
            'grid_in': len(extractor.grid_in_questions),
            'total': len(self.questions),
        }

        (self.output_dir / 'extraction_report.json').write_text(
            json.dumps(self.report.get('extraction', {}), indent=2), encoding='utf-8'
        )

    def _step_classify(self):
        if not self.questions:
            return
        classifier = SATClassifier(self.questions)
        self.questions = classifier.classify_all()
        self.report['classification'] = {
            'domain_distribution': classifier.domain_distribution(),
            'topic_distribution': classifier.topic_distribution(),
        }

    def _step_label_difficulty(self):
        if not self.questions:
            return
        labeler = DifficultyLabeler(self.questions)
        self.questions = labeler.label_all()
        self.report['difficulty'] = {'distribution': labeler.distribution()}

    def _step_detect_desmos(self):
        if not self.questions:
            return
        detector = DesmosDetector(self.questions)
        self.questions = detector.detect_all()
        self.report['desmos'] = {'distribution': detector.distribution()}

    def _step_explanations(self):
        if not self.questions:
            return
        gen = ExplanationGenerator(self.questions)
        self.questions = gen.generate_all()
        analyzer = MistakeAnalyzer(self.questions)
        self.report['mistake_analysis'] = analyzer.analyze_all()

    def _step_generate_mocks(self, num_mocks: int):
        if not self.questions:
            return
        generator = MockGenerator(self.questions)
        for i in range(num_mocks):
            test = generator.generate_full_test(seed=i + 1)
            self.mock_tests.append(test)
        self.report['mock_generation'] = {
            'tests_generated': num_mocks,
            'test_ids': [t['test_id'] for t in self.mock_tests],
        }

    def _step_validate(self):
        if not self.questions:
            return
        validator = QuestionValidator(self.questions)
        self.validation = validator.validate_all()
        self.report['validation'] = self.validation

    def _step_export(self):
        schema = DatabaseSchema(self.output_dir)
        paths = {}

        paths['questions'] = schema.export_questions_json(self.questions)
        paths['mock_tests'] = schema.export_mock_tests_json(self.mock_tests)

        paths['manifest'] = schema.export_manifest(
            self.questions, report=self.report.get('validation')
        )

        if self.questions:
            answer_keys = {}
            for q in self.questions:
                topic = q.get('topic', 'unknown')
                num = q.get('question_number_original', 0)
                answer_keys.setdefault(topic, {})[num] = q.get('correct_answer', '')
            (self.output_dir / 'answer_keys.json').write_text(
                json.dumps(answer_keys, ensure_ascii=False, indent=2), encoding='utf-8'
            )
            paths['answer_keys'] = self.output_dir / 'answer_keys.json'

        domains_path = self.output_dir / 'domain_summary.json'
        if 'classification' in self.report:
            domains_path.write_text(
                json.dumps(self.report['classification'], ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            paths['domain_summary'] = domains_path

        self.report['exported_files'] = {k: str(v) for k, v in paths.items()}
        self.report['output_dir'] = str(self.output_dir)

    def _save_pipeline_report(self):
        report_path = self.output_dir / 'pipeline_report.json'
        report_path.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def run_validation_only(self) -> dict[str, Any]:
        self.questions = self._load_existing_questions()
        if not self.questions:
            return {'error': 'No questions found to validate'}
        validator = QuestionValidator(self.questions)
        result = validator.validate_all()
        self.validation = result

        vpath = self.output_dir / 'validation_report.json'
        vpath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result

    def generate_mocks_only(self, num_mocks: int = 3) -> list[dict]:
        self.questions = self._load_existing_questions()
        if not self.questions:
            return []
        generator = MockGenerator(self.questions)
        self.mock_tests = [generator.generate_full_test(seed=i + 1) for i in range(num_mocks)]

        schema = DatabaseSchema(self.output_dir)
        schema.export_mock_tests_json(self.mock_tests)
        return self.mock_tests

    def _load_existing_questions(self) -> list[dict]:
        qpath = self.output_dir / 'questions.json'
        if qpath.exists():
            return json.loads(qpath.read_text(encoding='utf-8'))
        return self.questions
