import unittest
from unittest.mock import patch

from mac_tm_snapshot_doctor import cli


class SnapshotDoctorTest(unittest.TestCase):
    def test_parse_snapshot_list(self) -> None:
        text = """
Snapshots for volume group containing disk /:
com.apple.TimeMachine.2024-03-12-102045.local
com.apple.TimeMachine.2024-03-11-230900.local
"""
        ids = cli.parse_snapshot_list(text)
        self.assertEqual(len(ids), 2)
        self.assertIn("com.apple.TimeMachine.2024-03-12-102045.local", ids)
        self.assertIn("com.apple.TimeMachine.2024-03-11-230900.local", ids)

    def test_parse_snapshot_list_handles_noise(self) -> None:
        text = "No snapshots"
        ids = cli.parse_snapshot_list(text)
        self.assertEqual(ids, [])

    def test_find_tmutil_status_running(self) -> None:
        status = """
{
 \tRunning = 1;
 \tPhase = \"Copying\";
 \tBytes = 2048;
}
"""
        parsed = cli.find_tmutil_status(status)
        self.assertEqual(parsed["running"], True)
        self.assertEqual(parsed["phase"], '"Copying"')
        self.assertEqual(parsed["bytes"], 2048)

    @patch('mac_tm_snapshot_doctor.cli.run_tmutil')
    def test_list_snapshots_error(self, run_tmutil):
        run_tmutil.return_value = (1, "", "tmutil: command not found")
        result = cli.list_snapshots("/")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "tmutil: command not found")

    @patch('mac_tm_snapshot_doctor.cli.run_tmutil')
    def test_run_list_exit_code(self, run_tmutil):
        run_tmutil.return_value = (0, "com.apple.TimeMachine.2024-03-12-102045.local", "")
        self.assertEqual(cli.run_list("/", as_json=False), 0)


if __name__ == "__main__":
    unittest.main()
