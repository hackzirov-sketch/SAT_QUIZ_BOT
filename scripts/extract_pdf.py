#!/usr/bin/env python3
"""
Extract questions from Mathbook 3.0 PDF text, export as JSON.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from satmath.config import SATMathConfig
from satmath.question_extractor import QuestionExtractor


def main():
    parser = argparse.ArgumentParser(description='Extract SAT Math questions')
    parser.add_argument('--input', type=str, default=str(SATMathConfig.EXTRACTED_TEXT),
                        help='Path to extracted text file')
    parser.add_argument('--output', type=str, default='',
                        help='Output JSON file path')
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else (SATMathConfig.OUTPUT_DIR / 'questions.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    extractor = QuestionExtractor.from_file(args.input)
    questions = extractor.extract_all()

    output_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Extracted {len(questions)} questions ({len(extractor.questions)} MC, '
          f'{len(extractor.grid_in_questions)} grid-in)')
    print(f'Output: {output_path}')


if __name__ == '__main__':
    main()
