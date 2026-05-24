#!/usr/bin/env python3
"""
Run the full SAT Math pipeline: extract, classify, label, generate mocks, export.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from satmath.pipeline import Pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)


def main():
    parser = argparse.ArgumentParser(description='SAT Math Pipeline')
    parser.add_argument('--pdf', type=str, default='',
                        help='Path to Mathbook 3.0 PDF')
    parser.add_argument('--output', type=str, default='',
                        help='Output directory')
    parser.add_argument('--mocks', type=int, default=3,
                        help='Number of mock tests to generate')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only validate existing questions')
    parser.add_argument('--mocks-only', action='store_true',
                        help='Only generate mock tests from existing questions')
    parser.add_argument('--no-mocks', action='store_true',
                        help='Skip mock test generation')
    args = parser.parse_args()

    pipeline = Pipeline(
        pdf_path=args.pdf if args.pdf else None,
        output_dir=Path(args.output) if args.output else None,
    )

    if args.validate_only:
        result = pipeline.run_validation_only()
        print(f"Validation: {result.get('summary', 'N/A')}")
        if result.get('errors'):
            for e in result['errors'][:10]:
                print(f'  ERROR: {e}')
        return

    if args.mocks_only:
        tests = pipeline.generate_mocks_only(num_mocks=args.mocks)
        print(f'Generated {len(tests)} mock tests')
        return

    result = pipeline.run(
        generate_mocks=not args.no_mocks,
        num_mocks=args.mocks,
    )
    print(f'Pipeline completed: {result.get("total_questions", 0)} questions, '
          f'{result.get("mock_tests", 0)} mock tests')
    print(f'Output: {result.get("output_dir", "")}')


if __name__ == '__main__':
    main()
