#!/usr/bin/env python3
"""
Validate the SAT Math question bank — check fields, correctness, completeness.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from satmath.config import SATMathConfig
from satmath.validator import QuestionValidator
from satmath.answer_matcher import AnswerMatcher


def main():
    parser = argparse.ArgumentParser(description='Validate SAT Math question bank')
    parser.add_argument('--input', type=str, default='',
                        help='Path to questions.json')
    parser.add_argument('--answer-keys', type=str, default='',
                        help='Path to answer_keys.json for cross-validation')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed output')
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else (
        SATMathConfig.OUTPUT_DIR / 'questions.json'
    )
    if not input_path.exists():
        print(f'Error: questions not found at {input_path}')
        return

    questions = json.loads(input_path.read_text(encoding='utf-8'))

    validator = QuestionValidator(questions)
    result = validator.validate_all()

    print(result['summary'])
    print(f'  MC: {result["stats"].get("multiple_choice", 0)}')
    print(f'  Grid-In: {result["stats"].get("grid_in", 0)}')
    print(f'  Missing fields: {result["stats"].get("missing_fields", 0)}')

    if result['errors']:
        print(f'\nErrors ({len(result["errors"])}):')
        for e in result['errors'][:10]:
            print(f'  • {e}')
    else:
        print(f'\n✓ No errors')

    if result['warnings']:
        print(f'\nWarnings ({len(result["warnings"])}):')
        for w in result['warnings'][:10]:
            print(f'  • {w}')

    ak_path = Path(args.answer_keys) if args.answer_keys else (
        SATMathConfig.OUTPUT_DIR / 'answer_keys.json'
    )
    if ak_path.exists() and args.verbose:
        answer_sections = json.loads(ak_path.read_text(encoding='utf-8'))
        matcher = AnswerMatcher(questions, answer_sections)
        match_result = matcher.validate_all()
        print(f'\nAnswer key cross-validation:')
        print(f'  Matched: {match_result["matched_answers"]}')
        print(f'  Missing: {match_result["total_missing"]}')
        if match_result['suspicious_matches']:
            for m in match_result['suspicious_matches'][:5]:
                print(f'  MISMATCH: {m}')


if __name__ == '__main__':
    main()
