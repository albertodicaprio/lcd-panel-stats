"""Checks for service removal without touching the host's systemd state."""

import io
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import call, patch

import install


class RemoveServiceTests(TestCase):
    @patch("install.subprocess.run")
    @patch("install.Path.exists", return_value=True)
    def test_remove_stops_disables_deletes_and_reloads(self, exists, run):
        install.remove_service("client", dry_run=False)

        run.assert_has_calls([
            call(["sudo", "systemctl", "disable", "--now", "lcd-stats-client.service"], check=True),
            call(["sudo", "rm", "--", "/etc/systemd/system/lcd-stats-client.service"], check=True),
            call(["sudo", "systemctl", "daemon-reload"], check=True),
            call(["sudo", "rm", "--", "/etc/sudoers.d/lcd-stats-client"], check=True),
        ])
        self.assertEqual(run.call_count, 4)

    @patch("install.subprocess.run")
    @patch("install.Path.exists", return_value=True)
    def test_dry_run_shows_actions_without_running_them(self, exists, run):
        output = io.StringIO()
        with redirect_stdout(output):
            install.remove_service("server", dry_run=True)

        run.assert_not_called()
        self.assertIn("sudo systemctl disable --now lcd-stats-server.service", output.getvalue())
        self.assertIn("sudo rm -- /etc/systemd/system/lcd-stats-server.service", output.getvalue())
        self.assertIn("sudo systemctl daemon-reload", output.getvalue())

    @patch("install.subprocess.run")
    @patch("install.Path.exists", return_value=False)
    def test_absent_unit_is_safe_to_remove_again(self, exists, run):
        install.remove_service("client", dry_run=False)
        run.assert_not_called()

    @patch("install.subprocess.run")
    @patch("install.Path.exists", side_effect=[False, True])
    def test_remove_cleans_up_permission_even_if_unit_is_absent(self, exists, run):
        install.remove_service("client", dry_run=False)
        run.assert_called_once_with(["sudo", "rm", "--", "/etc/sudoers.d/lcd-stats-client"], check=True)


class ShutdownSudoersTests(TestCase):
    def test_policy_is_only_created_when_enabled(self):
        self.assertIsNone(install.shutdown_sudoers("[shutdown_button]\nenabled = false\n", "pi"))
        self.assertEqual(
            install.shutdown_sudoers("[shutdown_button]\nenabled = true\n", "pi"),
            "pi ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff\n",
        )

    @patch("install.subprocess.run")
    def test_install_validates_policy_before_installing(self, run):
        policy = "pi ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff\n"
        install.install_shutdown_sudoers(policy)
        run.assert_has_calls([
            call(["/usr/sbin/visudo", "-cf", "/dev/stdin"], input=policy, text=True, check=True),
            call(["sudo", "install", "-m", "0440", "/dev/stdin", "/etc/sudoers.d/lcd-stats-client"], input=policy, text=True, check=True),
        ])
