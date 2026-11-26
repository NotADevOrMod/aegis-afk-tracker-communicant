import json
import tempfile
import unittest
from pathlib import Path

from aegis_reconnect import config


class ConfigTest(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = config.load(Path(d) / "none.json")
        self.assertEqual(cfg.server_port, 25565)
        self.assertIsNone(cfg.calibration)

    def test_round_trip_keeps_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            cfg = config.Config(server_port=25570)
            cfg.calibration = config.Calibration(3, -12, [[1, 2, 3]] * 102, [[4, 5, 6]] * 102, scale=3, buttons_seen=2, rank_from_top=1)
            config.save(cfg, path)
            back = config.load(path)
        self.assertEqual(back.server_port, 25570)
        self.assertEqual((back.calibration.offset_x, back.calibration.offset_y), (3, -12))
        self.assertEqual(back.calibration.hover[0], [4, 5, 6])
        self.assertEqual((back.calibration.scale, back.calibration.buttons_seen, back.calibration.rank_from_top), (3, 2, 1))

    def test_unknown_keys_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            path.write_text(json.dumps({"server_port": 1234, "from_a_future_version": True}))
            cfg = config.load(path)
        self.assertEqual(cfg.server_port, 1234)


if __name__ == "__main__":
    unittest.main()
