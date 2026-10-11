import threading
import time
import unittest
from desktop_pet.events import usage_state
from desktop_pet.usage import parse_limits, snapshot_from_cache, read_usage, UsageError


def window(used=34, minutes=300):
    return {"usedPercent": used, "windowDurationMins": minutes, "resetsAt": int(time.time()) + 3600}


class UsageTests(unittest.TestCase):
    def test_multibucket_is_preferred_and_windows_use_duration(self):
        result = {"rateLimits": {"primary": window(99)}, "rateLimitsByLimitId": {
            "codex": {"primary": window(23, 10080), "secondary": window(34, 300)},
            "other": {"primary": window(15, 60)}}}
        snapshot = parse_limits(result)
        self.assertEqual(snapshot.buckets[0].window(300).remaining, 66)
        self.assertEqual(snapshot.buckets[0].window(10080).remaining, 77)
        self.assertIsNone(snapshot.buckets[1].window(300))

    def test_missing_and_invalid_usage_stays_unknown(self):
        for used in (None, "50", True, float("nan"), float("inf")):
            snapshot = parse_limits({"rateLimits": {"primary": window(used)}})
            self.assertIsNone(snapshot.buckets[0].window(300).remaining)

    def test_percent_clamps_and_threshold_boundaries(self):
        self.assertEqual(usage_state(50.1), "usage_normal")
        self.assertEqual(usage_state(50), "usage_low")
        self.assertEqual(usage_state(20), "usage_low")
        self.assertEqual(usage_state(19.9), "usage_critical")
        for used, expected in ((-1, 100), (101, 0)):
            snap = parse_limits({"rateLimits": {"primary": window(used)}})
            self.assertEqual(snap.buckets[0].window(300).remaining, expected)

    def test_no_data_is_not_zero(self):
        with self.assertRaises(UsageError):
            parse_limits({})

    def test_cache_preserves_original_timestamp(self):
        original = parse_limits({"rateLimits": {"primary": window()}}, 1700000000)
        restored = snapshot_from_cache(original.to_dict())
        self.assertEqual(original, restored)

    def test_invalid_executable_is_explicit(self):
        with self.assertRaises(UsageError):
            read_usage("E:/DesktopPet/does-not-exist.exe")


if __name__ == "__main__":
    unittest.main()
