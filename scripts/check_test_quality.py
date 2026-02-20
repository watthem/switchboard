#!/usr/bin/env python3
"""Static test-quality checks to catch low-value coverage padding."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Tautology:
    file: Path
    line: int
    test_name: str
    expr: str


@dataclass(frozen=True)
class NoAssertTest:
    file: Path
    line: int
    test_name: str


@dataclass
class FunctionStats:
    name: str
    line: int
    assert_count: int = 0
    status_code_asserts: int = 0

    @property
    def status_only(self) -> bool:
        return self.assert_count > 0 and self.assert_count == self.status_code_asserts


def _literal_key(node: ast.AST) -> tuple[str, object] | None:
    if isinstance(node, ast.Constant):
        return (type(node.value).__name__, node.value)
    return None


def _is_tautological_assert(test_expr: ast.AST) -> bool:
    if isinstance(test_expr, ast.Constant):
        return test_expr.value is True

    if isinstance(test_expr, ast.Compare):
        if len(test_expr.ops) == 1 and len(test_expr.comparators) == 1:
            left = test_expr.left
            right = test_expr.comparators[0]
            op = test_expr.ops[0]

            if isinstance(op, (ast.Eq, ast.Is)):
                left_lit = _literal_key(left)
                right_lit = _literal_key(right)
                if left_lit is not None and right_lit is not None:
                    return left_lit == right_lit

                if ast.dump(left, include_attributes=False) == ast.dump(
                    right, include_attributes=False
                ):
                    return True

    return False


def _is_status_code_expr(node: ast.AST) -> bool:
    current = node
    while isinstance(current, ast.Attribute):
        if current.attr == "status_code":
            return True
        current = current.value
    return False


def _is_status_code_assert(test_expr: ast.AST) -> bool:
    if not isinstance(test_expr, ast.Compare):
        return False
    if len(test_expr.ops) != 1 or len(test_expr.comparators) != 1:
        return False
    if not isinstance(test_expr.ops[0], ast.Eq):
        return False

    left = test_expr.left
    right = test_expr.comparators[0]
    left_is_status = _is_status_code_expr(left)
    right_is_status = _is_status_code_expr(right)
    if left_is_status == right_is_status:
        return False

    other = right if left_is_status else left
    return isinstance(other, ast.Constant) and isinstance(other.value, int)


def _format_expr(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparseable>"


def _iter_test_functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield node


def collect_stats(
    tests_dir: Path,
) -> tuple[int, int, list[Tautology], list[NoAssertTest], int, int]:
    files = sorted(
        path
        for path in tests_dir.rglob("*.py")
        if "__pycache__" not in path.parts and path.is_file()
    )

    file_count = len(files)
    test_functions = 0
    total_asserts = 0
    tautologies: list[Tautology] = []
    no_assert_tests: list[NoAssertTest] = []
    status_only_tests = 0

    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for func in _iter_test_functions(tree):
            test_functions += 1
            stats = FunctionStats(name=func.name, line=func.lineno)
            for node in ast.walk(func):
                if isinstance(node, ast.Assert):
                    stats.assert_count += 1
                    if _is_status_code_assert(node.test):
                        stats.status_code_asserts += 1
                    if _is_tautological_assert(node.test):
                        tautologies.append(
                            Tautology(
                                file=file_path,
                                line=node.lineno,
                                test_name=func.name,
                                expr=_format_expr(node.test),
                            )
                        )

            total_asserts += stats.assert_count
            if stats.assert_count == 0:
                no_assert_tests.append(
                    NoAssertTest(file=file_path, line=stats.line, test_name=stats.name)
                )
            elif stats.status_only:
                status_only_tests += 1

    return file_count, test_functions, tautologies, no_assert_tests, total_asserts, status_only_tests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect low-value test padding (e.g. assert True, status-only tests)."
    )
    parser.add_argument("--tests-dir", default="tests", help="Directory containing tests.")
    parser.add_argument(
        "--max-status-only-ratio",
        type=float,
        default=0.35,
        help="Maximum allowed ratio of status-code-only tests.",
    )
    parser.add_argument(
        "--min-tests-for-ratio",
        type=int,
        default=20,
        help="Only enforce ratio when at least this many tests are present.",
    )
    args = parser.parse_args()

    tests_dir = Path(args.tests_dir)
    if not tests_dir.exists():
        print(f"FAIL: tests directory not found: {tests_dir}")
        return 2

    (
        file_count,
        test_functions,
        tautologies,
        no_assert_tests,
        total_asserts,
        status_only_tests,
    ) = collect_stats(tests_dir)

    status_ratio = (status_only_tests / test_functions) if test_functions else 0.0

    print("Test Quality Report")
    print(f"- files scanned: {file_count}")
    print(f"- test functions: {test_functions}")
    print(f"- total asserts: {total_asserts}")
    print(f"- tautological asserts: {len(tautologies)}")
    print(f"- tests with no asserts: {len(no_assert_tests)}")
    print(
        f"- status-code-only tests: {status_only_tests} ({status_ratio:.1%}, limit {args.max_status_only_ratio:.1%})"
    )

    if tautologies:
        print("\nTautological assertions (remove/replace):")
        for item in tautologies:
            print(f"- {item.file}:{item.line} ({item.test_name}): assert {item.expr}")

    if no_assert_tests:
        print("\nTests with no assertions (likely placeholders):")
        for item in no_assert_tests:
            print(f"- {item.file}:{item.line} ({item.test_name})")

    failures: list[str] = []
    if tautologies:
        failures.append("tautological assertions found")
    if no_assert_tests:
        failures.append("tests with no assertions found")
    if test_functions >= args.min_tests_for_ratio and status_ratio > args.max_status_only_ratio:
        failures.append(
            f"status-code-only test ratio too high ({status_ratio:.1%} > {args.max_status_only_ratio:.1%})"
        )

    if failures:
        print("\nFAIL:")
        for reason in failures:
            print(f"- {reason}")
        return 1

    print("\nPASS: test quality checks look healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
