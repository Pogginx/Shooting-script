#!/usr/bin/env python3

from decimal import Decimal
import unittest

from validate_timeline import parse_timeline, validate_timeline


class TimelineValidationTests(unittest.TestCase):
    def test_valid_contiguous_timeline(self) -> None:
        shots, parse_errors = parse_timeline(
            ["S001\t0\t3.5\n", "S002\t3.5\t7\n", "S003\t7\t12\n"]
        )
        errors, warnings = validate_timeline(shots, target=Decimal("12"))
        self.assertEqual(parse_errors, [])
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_detects_gap_and_wrong_target(self) -> None:
        shots, _ = parse_timeline(["S001,0,3\n", "S002,4,8\n"])
        errors, _ = validate_timeline(shots, target=Decimal("10"))
        self.assertTrue(any("gap of 1s" in error for error in errors))
        self.assertTrue(any("target is 10s" in error for error in errors))

    def test_detects_overlap_and_duplicate_id(self) -> None:
        shots, _ = parse_timeline(["S001 0 5\n", "S001 4 8\n"])
        errors, _ = validate_timeline(shots, target=Decimal("8"))
        self.assertTrue(any("duplicate shot id" in error for error in errors))
        self.assertTrue(any("overlap of 1s" in error for error in errors))

    def test_warns_for_duration_band(self) -> None:
        shots, _ = parse_timeline(["S001 0 1\n", "S002 1 8\n"])
        errors, warnings = validate_timeline(
            shots,
            target=Decimal("8"),
            min_shot=Decimal("2"),
            max_shot=Decimal("6"),
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)


if __name__ == "__main__":
    unittest.main()
