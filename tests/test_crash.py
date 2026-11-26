import unittest

from aegis_reconnect.crash import CrashFile, CrashKind, classify

NOW = 10_000.0


class CrashTest(unittest.TestCase):
    def test_recent_crash_report_is_a_java_crash(self):
        v = classify(NOW, [CrashFile("crash-2026-11-26_10.00.00-client.txt", NOW - 20)], 0, 60)
        self.assertEqual(v.kind, CrashKind.JAVA_CRASH)
        self.assertTrue(v.is_crash)

    def test_jvm_log_wins_over_a_crash_report(self):
        files = [CrashFile("crash-x.txt", NOW - 10), CrashFile("hs_err_pid4242.log", NOW - 5)]
        self.assertEqual(classify(NOW, files, 0, 60).kind, CrashKind.NATIVE_CRASH)

    def test_old_crash_reports_are_ignored(self):
        v = classify(NOW, [CrashFile("crash-old.txt", NOW - 86_400)], 0, 60)
        self.assertEqual(v.kind, CrashKind.CLEAN_EXIT)

    def test_vanishing_while_you_were_away_is_suspicious(self):
        self.assertEqual(classify(NOW, [], 600, 60).kind, CrashKind.VANISHED_IDLE)

    def test_closing_it_yourself_is_not_a_crash(self):
        v = classify(NOW, [], 3, 60)
        self.assertEqual(v.kind, CrashKind.CLEAN_EXIT)
        self.assertFalse(v.is_crash)


if __name__ == "__main__":
    unittest.main()
