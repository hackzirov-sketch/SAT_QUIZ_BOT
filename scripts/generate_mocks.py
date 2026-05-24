#!/usr/bin/env python3
"""
Generate SAT Math mock tests from existing question bank (questions.json).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from satmath.mock_generator import MockGenerator
from satmath.scoring_engine import ScoringEngine


def main():
    parser = argparse.ArgumentParser(description='Generate SAT Math mock tests')
    parser.add_argument('--input', type=str, default='',
                        help='Path to questions.json')
    parser.add_argument('--count', type=int, default=3,
                        help='Number of mock tests to generate')
    parser.add_argument('--output', type=str, default='',
                        help='Output directory')
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else Path(__file__).parent.parent / 'output' / 'questions.json'
    if not input_path.exists():
        print(f'Error: questions not found at {input_path}')
        return

    questions = json.loads(input_path.read_text(encoding='utf-8'))
    output_dir = Path(args.output) if args.output else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = MockGenerator(questions)
    tests = [generator.generate_full_test(seed=i + 1) for i in range(args.count)]

    (output_dir / 'mock_tests.json').write_text(
        json.dumps(tests, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f'Generated {len(tests)} mock tests')
    for test in tests:
        for m in test.get('modules', []):
            mc = m.get('multiple_choice', 0)
            gi = m.get('grid_in', 0)
            print(f'  {test["test_id"]} — Module {m["module_number"]}: {mc} MC + {gi} Grid-In')


if __name__ == '__main__':
    main()
