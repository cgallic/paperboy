from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from paperboy.config import PaperboyConfig


class ConfigTests(unittest.TestCase):
    def test_defaults_are_sane(self) -> None:
        cfg = PaperboyConfig()
        self.assertEqual(cfg.fast_model, "llama3.2:3b")
        self.assertEqual(cfg.research_model, "qwen2.5:7b")
        self.assertEqual(cfg.prompt_digest_limit, 12)
        self.assertTrue(1 <= cfg.papers_max_per_run <= 10)

    def test_db_path_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            os.environ["PAPERBOY_DB"] = str(Path(td) / "custom.db")
            cfg = PaperboyConfig()
            self.assertEqual(str(cfg.db_path), os.environ["PAPERBOY_DB"])
            del os.environ["PAPERBOY_DB"]

    def test_log_level_validation(self) -> None:
        cfg = PaperboyConfig(log_level="DEBUG")
        self.assertEqual(cfg.log_level, "DEBUG")
        with self.assertRaises(ValueError):
            PaperboyConfig(log_level="VERBOSE")

    def test_relevance_bounds(self) -> None:
        with self.assertRaises(ValueError):
            PaperboyConfig(papers_min_relevance=11)
        with self.assertRaises(ValueError):
            PaperboyConfig(action_queue_min_relevance=-1)


if __name__ == "__main__":
    unittest.main()
