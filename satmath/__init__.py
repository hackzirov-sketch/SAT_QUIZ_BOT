from __future__ import annotations

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
from satmath.pipeline import Pipeline

__version__ = '1.1.0'
