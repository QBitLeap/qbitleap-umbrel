from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class DashboardTelemetryTests(unittest.TestCase):
    def test_reads_permissionless_telemetry(self):
        telemetry = {
            "connected_workers": 1,
            "current_hashrate_hs": 9_750_000_000_000,
            "accepted_shares": 12,
            "rejected_shares": 1,
            "updated_at": 1_788_300_000,
            "workers": [
                {"worker": "qb1address.thor-p2", "active": True, "last_share_at": 1_788_300_000}
            ],
            "block_history": {
                "qbit": [
                    {
                        "height": 69932,
                        "block_hash": "0000abc",
                        "worker": "thor-p2",
                        "found_at": 1_788_300_000,
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            telemetry_path = Path(directory) / "telemetry.json"
            telemetry_path.write_text(json.dumps(telemetry), encoding="utf-8")
            with patch.object(main, "PERMISSIONLESS_TELEMETRY_FILE", telemetry_path):
                stats = main.read_ckpool_stats()

        self.assertEqual(stats["workers"], 1)
        self.assertEqual(stats["hashrate_1m"], "9.75 TH/s")
        self.assertEqual(stats["accepted"], "12")
        self.assertEqual(stats["rejected"], "1")
        self.assertEqual(stats["blocks_found"], "1")
        self.assertEqual(stats["block_history"][0]["height"], 69932)

    def test_hall_deduplicates_one_block_reported_by_multiple_sources(self):
        events = [
            {"height": 69932, "block_hash": "0000abc", "worker": "thor-p2", "found_at": 1000},
            {"height": 69932, "block_hash": "0000abc", "worker": "permissionless miner", "found_at": 1001},
        ]
        with tempfile.TemporaryDirectory() as directory:
            hall_path = Path(directory) / "hall.json"
            with patch.object(main, "HALL_OF_BLOCKS_PATH", hall_path):
                hall = main.update_hall_of_blocks(2, "qb1address", None, 100, events)

        self.assertEqual(len(hall["blocks"]), 1)
        self.assertEqual(hall["blocks"][0]["height"], 69932)

    def test_enriches_migrated_block_with_coinbase_reward(self):
        existing = {
            "observed_blocks_found": 1,
            "blocks": [{
                "height": 69932,
                "block_hash": "0000abc",
                "reward": "Paid directly to configured Qbit address",
            }],
        }
        coinbase = {"tx": [{"vout": [{"value": 25}, {"value": 0.125}]}]}
        with tempfile.TemporaryDirectory() as directory:
            hall_path = Path(directory) / "hall.json"
            hall_path.write_text(json.dumps(existing), encoding="utf-8")
            with patch.object(main, "HALL_OF_BLOCKS_PATH", hall_path), patch.object(
                main, "rpc", return_value=coinbase
            ):
                hall = main.update_hall_of_blocks(1, "qb1address", None, 100, [])

        self.assertEqual(hall["blocks"][0]["reward"], "25.12500000 QBIT")

    def test_hall_removes_legacy_hashless_false_block(self):
        events = [{
            "height": 74055,
            "block_hash": "0000abc",
            "worker": "thor-p2",
            "found_at": 1000,
        }]
        legacy_hall = {
            "observed_blocks_found": 2,
            "blocks": [
                {"height": 74055, "block_hash": "0000abc", "finder": "permissionless miner"},
                {"height": 74056, "finder": "thor-p2"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            hall_path = Path(directory) / "hall.json"
            hall_path.write_text(json.dumps(legacy_hall), encoding="utf-8")
            with patch.object(main, "HALL_OF_BLOCKS_PATH", hall_path):
                hall = main.update_hall_of_blocks(1, "qb1address", None, 100, events)

        self.assertEqual([block["height"] for block in hall["blocks"]], [74055])
        self.assertEqual(hall["observed_blocks_found"], 1)


if __name__ == "__main__":
    unittest.main()
