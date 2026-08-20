#!/usr/bin/env python3
"""Validate a master-shot timeline exported as ID/start/end rows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys
from typing import Iterable, TextIO


@dataclass(frozen=True)
class Shot:
    shot_id: str
    start: Decimal
    end: Decimal
    line_number: int

    @property
    def duration(self) -> Decimal:
        return self.end - self.start


def _split_row(line: str) -> list[str]:
    if "\t" in line:
        return [part.strip() for part in line.split("\t")]
    if "," in line:
        return [part.strip() for part in line.split(",")]
    return line.split()


def parse_timeline(lines: Iterable[str]) -> tuple[list[Shot], list[str]]:
    shots: list[Shot] = []
    errors: list[str] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = _split_row(line)
        if len(parts) != 3:
            errors.append(
                f"line {line_number}: expected 3 fields (id, start, end), got {len(parts)}"
            )
            continue

        shot_id, start_text, end_text = parts
        if not shots and start_text.lower() == "start" and end_text.lower() == "end":
            continue

        try:
            start = Decimal(start_text)
            end = Decimal(end_text)
        except InvalidOperation:
            errors.append(
                f"line {line_number}: start/end must be numeric, got {start_text!r}/{end_text!r}"
            )
            continue

        shots.append(Shot(shot_id=shot_id, start=start, end=end, line_number=line_number))

    if not shots and not errors:
        errors.append("timeline contains no shots")
    return shots, errors


def validate_timeline(
    shots: list[Shot],
    target: Decimal,
    tolerance: Decimal = Decimal("0.001"),
    min_shot: Decimal | None = None,
    max_shot: Decimal | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for shot in shots:
        if shot.shot_id in seen_ids:
            errors.append(f"line {shot.line_number}: duplicate shot id {shot.shot_id!r}")
        seen_ids.add(shot.shot_id)

        if shot.start < 0:
            errors.append(f"{shot.shot_id}: start time is negative ({shot.start})")
        if shot.end <= shot.start:
            errors.append(
                f"{shot.shot_id}: end ({shot.end}) must be greater than start ({shot.start})"
            )

        if min_shot is not None and shot.duration < min_shot:
            warnings.append(
                f"{shot.shot_id}: duration {shot.duration}s is below {min_shot}s"
            )
        if max_shot is not None and shot.duration > max_shot:
            warnings.append(
                f"{shot.shot_id}: duration {shot.duration}s exceeds {max_shot}s"
            )

    if not shots:
        return errors, warnings

    if abs(shots[0].start) > tolerance:
        errors.append(f"timeline must start at 0s, starts at {shots[0].start}s")

    for previous, current in zip(shots, shots[1:]):
        delta = current.start - previous.end
        if delta > tolerance:
            errors.append(
                f"gap of {delta}s between {previous.shot_id} and {current.shot_id}"
            )
        elif delta < -tolerance:
            errors.append(
                f"overlap of {-delta}s between {previous.shot_id} and {current.shot_id}"
            )

    final_end = shots[-1].end
    if abs(final_end - target) > tolerance:
        errors.append(f"timeline ends at {final_end}s, target is {target}s")

    return errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate shot IDs and contiguous start/end times in a TSV, CSV, or whitespace file."
    )
    parser.add_argument(
        "timeline",
        nargs="?",
        type=Path,
        help="Timeline file. Reads standard input when omitted.",
    )
    parser.add_argument("--target", required=True, type=Decimal, help="Required total duration.")
    parser.add_argument(
        "--tolerance",
        type=Decimal,
        default=Decimal("0.001"),
        help="Allowed numeric tolerance in seconds (default: 0.001).",
    )
    parser.add_argument("--min-shot", type=Decimal, help="Warn below this shot duration.")
    parser.add_argument("--max-shot", type=Decimal, help="Warn above this shot duration.")
    return parser


def _open_input(path: Path | None) -> tuple[TextIO, bool]:
    if path is None:
        return sys.stdin, False
    return path.open("r", encoding="utf-8"), True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        stream, should_close = _open_input(args.timeline)
    except OSError as exc:
        print(f"ERROR: could not read timeline: {exc}", file=sys.stderr)
        return 2

    try:
        shots, parse_errors = parse_timeline(stream)
    finally:
        if should_close:
            stream.close()

    errors, warnings = validate_timeline(
        shots,
        target=args.target,
        tolerance=args.tolerance,
        min_shot=args.min_shot,
        max_shot=args.max_shot,
    )
    errors = parse_errors + errors

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        return 1

    print(f"OK: {len(shots)} shots, continuous 0–{args.target}s timeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
