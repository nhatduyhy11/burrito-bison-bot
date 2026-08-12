#!/usr/bin/env python3
"""Inventory the tools directory and flag similarly named Python functions."""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union


DEFAULT_TREE_OUTPUT = "tools_tree.txt"
DEFAULT_FUNCTIONS_OUTPUT = "tools_python_functions.txt"
DEFAULT_DUPLICATES_OUTPUT = "tools_possible_duplicate_functions.txt"


@dataclass(frozen=True)
class FunctionInfo:
    file: Path
    qualified_name: str
    name: str
    line: int
    is_async: bool

    def location(self) -> str:
        return f"{self.file.as_posix()}:{self.line}::{self.qualified_name}"


class FunctionCollector(ast.NodeVisitor):
    """Collect functions, methods, and nested functions with qualified names."""

    def __init__(self, relative_file: Path) -> None:
        self.relative_file = relative_file
        self.scope: List[str] = []
        self.functions: List[FunctionInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], *, is_async: bool
    ) -> None:
        qualified_name = ".".join([*self.scope, node.name])
        self.functions.append(
            FunctionInfo(
                file=self.relative_file,
                qualified_name=qualified_name,
                name=node.name,
                line=node.lineno,
                is_async=is_async,
            )
        )
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def visible_entries(directory: Path) -> List[Path]:
    return sorted(
        (entry for entry in directory.iterdir() if entry.suffix.lower() != ".png"),
        key=lambda entry: (not entry.is_dir(), entry.name.casefold()),
    )


def render_tree(root: Path) -> str:
    lines = [f"{root.name}/"]

    def walk(directory: Path, prefix: str) -> None:
        entries = visible_entries(directory)
        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension)

    walk(root, "")
    return "\n".join(lines) + "\n"


def python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py"), key=lambda item: item.as_posix().casefold()):
        if "__pycache__" not in path.parts:
            yield path


def collect_functions(
    root: Path,
) -> Tuple[List[FunctionInfo], List[str], List[Path]]:
    functions: List[FunctionInfo] = []
    errors: List[str] = []
    scanned_files: List[Path] = []
    base = root.parent

    for path in python_files(root):
        relative_file = path.relative_to(base)
        scanned_files.append(relative_file)
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(relative_file))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"{relative_file.as_posix()}: {exc}")
            continue
        collector = FunctionCollector(relative_file)
        collector.visit(tree)
        functions.extend(collector.functions)

    return functions, errors, scanned_files


def split_name(name: str) -> List[str]:
    without_dunders = name.strip("_")
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", without_dunders)
    return [token for token in re.split(r"[^a-zA-Z0-9]+", camel_split.lower()) if token]


def duplicate_score(left: str, right: str) -> Optional[Tuple[float, str]]:
    if left == right:
        return 1.0, "exact same function name"

    left_tokens = split_name(left)
    right_tokens = split_name(right)
    if not left_tokens or not right_tokens:
        return None

    left_compact = "".join(left_tokens)
    right_compact = "".join(right_tokens)
    if left_compact == right_compact:
        return 0.99, "same normalized name"

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    shared = left_set & right_set
    union = left_set | right_set
    jaccard = len(shared) / len(union)
    sequence = SequenceMatcher(None, left_compact, right_compact).ratio()

    if len(shared) >= 2 and left_set == right_set:
        return 0.97, "same name tokens in a different order"
    if len(shared) >= 2 and jaccard >= 0.75:
        return round(max(0.88, jaccard), 2), "nearly identical name tokens"
    if min(len(left_compact), len(right_compact)) >= 8 and sequence >= 0.86:
        return round(sequence, 2), "high normalized-name similarity"
    if len(shared) >= 2 and (left_set < right_set or right_set < left_set):
        return 0.84, "one function name extends the other"
    return None


def possible_duplicates(
    functions: Sequence[FunctionInfo],
) -> List[Tuple[float, str, FunctionInfo, FunctionInfo]]:
    matches: List[Tuple[float, str, FunctionInfo, FunctionInfo]] = []
    candidates = [function for function in functions if not function.name.startswith("__")]
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            result = duplicate_score(left.name, right.name)
            if result is not None:
                score, reason = result
                matches.append((score, reason, left, right))
    return sorted(
        matches,
        key=lambda match: (
            -match[0],
            match[2].name.casefold(),
            match[3].name.casefold(),
            match[2].location(),
        ),
    )


def render_functions(
    functions: Sequence[FunctionInfo],
    errors: Sequence[str],
    scanned_files: Sequence[Path],
) -> str:
    lines = [
        "Python functions defined under tools/",
        "Generated with Python AST; __pycache__ directories are ignored.",
        "",
    ]
    for file_index, scanned_file in enumerate(scanned_files):
        if file_index:
            lines.append("")
        lines.append(f"[{scanned_file.as_posix()}]")
        file_functions = [
            function for function in functions if function.file == scanned_file
        ]
        if not file_functions:
            lines.append("  (no functions defined)")
        for function in file_functions:
            kind = "async def" if function.is_async else "def"
            lines.append(f"  L{function.line}: {kind} {function.qualified_name}")

    if not scanned_files:
        lines.append("(no Python files found)")
    if errors:
        lines.extend(["", "Parse/read errors:"])
        lines.extend(f"  - {error}" for error in errors)
    return "\n".join(lines) + "\n"


def render_duplicates(
    matches: Sequence[Tuple[float, str, FunctionInfo, FunctionInfo]],
) -> str:
    lines = [
        "Possible duplicate-function candidates (name-only heuristic)",
        "No function bodies, calls, or behavior were compared. Review manually.",
        "",
    ]
    if not matches:
        lines.append("(no suspicious pairs found)")
    for index, (score, reason, left, right) in enumerate(matches, start=1):
        lines.extend(
            [
                f"{index}. score={score:.2f} — {reason}",
                f"   - {left.location()}",
                f"   - {right.location()}",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("tools"))
    parser.add_argument("--tree-output", type=Path, default=Path(DEFAULT_TREE_OUTPUT))
    parser.add_argument(
        "--functions-output", type=Path, default=Path(DEFAULT_FUNCTIONS_OUTPUT)
    )
    parser.add_argument(
        "--duplicates-output", type=Path, default=Path(DEFAULT_DUPLICATES_OUTPUT)
    )
    return parser.parse_args()


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    functions, errors, scanned_files = collect_functions(root)
    matches = possible_duplicates(functions)
    write_report(args.tree_output, render_tree(root))
    write_report(
        args.functions_output, render_functions(functions, errors, scanned_files)
    )
    write_report(args.duplicates_output, render_duplicates(matches))

    print(f"Tree: {args.tree_output} (PNG files skipped)")
    print(f"Functions: {args.functions_output} ({len(functions)} found)")
    print(f"Duplicate candidates: {args.duplicates_output} ({len(matches)} pairs)")
    if errors:
        print(f"Warnings: {len(errors)} Python file(s) could not be parsed/read")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
