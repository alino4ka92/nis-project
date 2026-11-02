"""Checks for invalid measurement series that must not enter the analysis."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from summarize_metrics import METRICS, summarize


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.run = {"run_id": "test", "status": "complete", "queries": 1, "measured_runs": 3}
        self.rows = []
        for repeat, value in enumerate([0, 7, 2], 1):
            self.rows.append({"query_number": 1, "repeat": repeat,
                              "query_id": f"test-q1-measure{repeat}",
                              **dict.fromkeys(METRICS, value)})

    def execute(self):
        (self.directory / "run.json").write_text(json.dumps(self.run))
        (self.directory / "measurements.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in self.rows)
        )
        return summarize(self.directory)

    def test_zero_and_outlier_are_preserved(self):
        row = self.execute()[0]
        self.assertEqual((row["elapsed_ms_median"], row["elapsed_ms_min"], row["elapsed_ms_max"]), (2, 0, 7))

    def test_incomplete_or_duplicate_series_rejected(self):
        for rows in (self.rows[:2], self.rows + self.rows[:1]):
            with self.subTest(rows=len(rows)):
                original = self.rows
                self.rows = rows
                with self.assertRaises(ValueError):
                    self.execute()
                self.rows = original

    def test_warmup_or_other_run_rejected(self):
        for query_id in ("test-q1-warm1", "other-q1-measure1"):
            with self.subTest(query_id=query_id):
                self.rows[0]["query_id"] = query_id
                with self.assertRaises(ValueError):
                    self.execute()

    def test_missing_or_invalid_metric_rejected(self):
        for value in (None, -1, True, "2"):
            with self.subTest(value=value):
                self.rows[0]["cpu_time_us"] = value
                with self.assertRaises(ValueError):
                    self.execute()

    def test_unavailable_cpu_counters_rejected(self):
        self.rows[0]["has_cpu_events"] = 0
        with self.assertRaises(ValueError):
            self.execute()

    def test_cpu_components_must_match_total(self):
        self.rows[0].update({"user_cpu_time_us": 2, "system_cpu_time_us": 3})
        with self.assertRaises(ValueError):
            self.execute()

    def test_queries_summarized_separately(self):
        self.run["queries"] = 2
        for repeat in range(1, 4):
            self.rows.append({"query_number": 2, "repeat": repeat,
                              "query_id": f"test-q2-measure{repeat}",
                              **dict.fromkeys(METRICS, 100)})
        result = self.execute()
        self.assertEqual([row["elapsed_ms_median"] for row in result], [2, 100])

    def test_failed_run_rejected(self):
        self.run["status"] = "failed"
        with self.assertRaises(ValueError):
            self.execute()


if __name__ == "__main__":
    unittest.main()
